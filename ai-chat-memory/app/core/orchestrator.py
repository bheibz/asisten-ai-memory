import asyncio
import logging
import re
from typing import AsyncGenerator

from app.core.query_classifier import QueryClassifier
from app.core.prompt_compiler import PromptCompiler
from app.core.model_router import ModelRouter
from app.memory.memory_manager import MemoryManager
from app.llm.gateway import llm_gateway
from app.db.redis_client import redis_client
from app.tools.web_search import web_search

logger = logging.getLogger(__name__)

MEMORY_COMMANDS = {
    "ganti_namamu": r"(?:aku\s+)?(?:ganti|ubah|set|panggil)\s+(?:(?:nama\s+)?kamu|namamu)\s+(?:menjadi|jadi|:)?\s*([a-zA-Z0-9_]+)",
    "ganti_namaku": r"(?:aku\s+)?(?:ganti|ubah|set|panggil)\s+(?:(?:nama\s+)?(?:aku|saya)|namaku)\s+(?:menjadi|jadi|:)?\s*([a-zA-Z0-9_]+)",
    "ingat": r"(?:ingat|catat|remember|save|note)\s+(?:bahwa|:|\s)?\s*(.+)",
    "lupa": r"(?:lupa|forget|hapus|delete|remove)\s+(?:bahwa|:|\s)?\s*(.+)",
    "update": r"(?:perbaharui|ubah|update|ganti|edit|change)\s+(?:catatan|memory|memori|note)?\s*(?:tentang|mengenai|:)?\s*(.+)",
}

FOLLOWUP_WORDS = {"terus", "lanjut", "detail", "jelasin", "jelaskan", "lebih", "coba lagi", "cari", "cek", "lagi"}

KNOWLEDGE_COMMANDS = {
    "simpan": r"(?:simpan|catat|save|note)\s+(?:catatan|knowledge|pengetahuan)?\s*[:\-]?\s*([\s\S]+)",
    "cari_catatan": r"(?:cari|search)\s+(?:di\s+)?(?:catatan|knowledge|notes|pengetahuan)\s+(.+)",
}
SAD_WORDS = {"sedih", "kecewa", "sakit", "lelah", "sendiri", "betah", "pusing", "rindu", "kehilangan", "menangis"}
ANGRY_WORDS = {"marah", "kesal", "sebal", "geram", "jengkel", "muak", "jijik", "benci"}
HAPPY_WORDS = {"senang", "bahagia", "syukur", "ceria", "happy", "seneng", "syukur", "bangga", "terharu"}
ANXIOUS_WORDS = {"cemas", "khawatir", "takut", "gelisah", "deg", "debar", "panic"}
TIRED_WORDS = {"capek", "lelah", "mengantuk", "letih", "lesu", "tired", "exhausted"}


class BrainOrchestrator:

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.classifier = QueryClassifier()
        self.prompt_compiler = PromptCompiler()
        self.router = ModelRouter(llm_gateway=llm_gateway)
        self.model_override = None

    def _get_last_user_msg(self, working_mem: list) -> str:
        for m in reversed(working_mem):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

    def _detect_tone(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ANXIOUS_WORDS): return "anxious"
        if any(w in msg for w in SAD_WORDS): return "sympathetic"
        if any(w in msg for w in TIRED_WORDS): return "tired"
        if any(w in msg for w in ANGRY_WORDS): return "calm"
        if any(w in msg for w in HAPPY_WORDS): return "cheerful"
        return "neutral"

    async def _handle_cmd_reminder(self, user_id: str, message: str, raw_query: str):
        import dateparser
        from datetime import datetime
        when = dateparser.parse(raw_query, languages=["id", "en"])
        if not when:
            when = dateparser.parse("besok", languages=["id"])
        from app.db.database import async_session
        from app.db.postgres import PostgresDB
        async with async_session() as session:
            db = PostgresDB(session)
            await db.create_reminder(user_id, message, when)
        return when

    async def _execute_cmd(self, cmd_type: str, cmd_val: str, user_id: str) -> str | None:
        from app.db.database import async_session
        from app.db.postgres import PostgresDB
        from app.llm.embeddings import Embedder
        if cmd_type == "reminder":
            parts = cmd_val.split(":", 1)
            msg = parts[0]
            when = parts[1] if len(parts) > 1 else "besok"
            dt = await self._handle_cmd_reminder(user_id, msg, when)
            return f"✅ Reminder disimpan: *{msg}* ({dt.strftime('%d %b %Y %H:%M') if dt else 'besok'})"
        async with async_session() as session:
            db = PostgresDB(session)
            embedder = Embedder()
            memory = MemoryManager(db, embedder)
            user = await db.get_user(user_id)
            if not user:
                from app.db.models import User as UserModel
                from sqlalchemy import insert
                await session.execute(insert(UserModel).values(id=user_id, username=user_id))
                await session.commit()
            if cmd_type == "ganti_namamu":
                await db.set_preferred_ai_name(user_id, cmd_val)
                return f"✅ Oke, panggil aku *{cmd_val}* mulai sekarang!"
            if cmd_type == "ganti_namaku":
                profile = await db.get_user_profile(user_id)
                profile["name"] = cmd_val
                await db.update_user_profile(user_id, profile)
                return f"✅ Senang kenal, *{cmd_val}*!"
            if cmd_type == "ingat":
                words = cmd_val.split()
                skip = {"aku", "saya", "my", "i", "gue", "gw"}
                key = words[1] if len(words) >= 2 and words[0] in skip else words[0] if words else "catatan"
                existing = await db.find_fact(user_id, "personal", key)
                if existing:
                    await db.update_fact(existing.id, cmd_val)
                    from app.db.vector_store import vector_store
                    await vector_store.delete(existing.id)
                    embed = await embedder.embed(f"{key}: {cmd_val}")
                    await vector_store.upsert("user_memories", existing.id, embed, {
                        "id": existing.id, "user_id": user_id, "fact_type": "personal",
                        "content": f"{key}: {cmd_val}", "decay_score": 1.0, "access_count": 0,
                    })
                else:
                    await memory.long_term.store_fact(user_id, None, {"type": "personal", "key": key, "value": cmd_val})
                return f"✅ Disimpan! *{cmd_val}*"
            if cmd_type == "lupa":
                facts = await db.get_user_facts(user_id)
                for f in facts:
                    if cmd_val.lower() in f.fact_value.lower() or cmd_val.lower() in f.fact_key.lower():
                        await db.delete_fact(f.id)
                        from app.db.vector_store import vector_store
                        await vector_store.delete(f.id)
                        return f"🗑️ Dihapus: *{f.fact_key}: {f.fact_value}*"
                return f"🔍 Tidak nemu *{cmd_val}*"
        return None

    async def process_message(self, user_id: str, conversation_id: str, message: str) -> AsyncGenerator[str, None]:
        query = await self.classifier.classify(message)
        memory_result = await self._handle_memory_command(user_id, message)
        if memory_result:
            yield memory_result
            return
        cached = await redis_client.get_response(message, user_id)
        if cached:
            yield cached
            return

        yield "\n__STATUS__:🧠 Mengingat memori...\n"
        working_mem, relevant_mem, user_profile = await asyncio.gather(
            self.memory.get_working_memory(user_id, conversation_id),
            self.memory.retrieve_relevant(user_id, message, top_k=5),
            self.memory.get_user_profile(user_id),
        )

        if not relevant_mem:
            all_facts = await self.memory.long_term.retrieve_all(user_id)
            if all_facts:
                relevant_mem = all_facts[:5]

        from datetime import datetime
        now = datetime.now()
        days = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
        months_id = ["Januari","Februari","Maret","April","Mei","Juni",
                     "Juli","Agustus","September","Oktober","November","Desember"]

        msg_lower = message.lower().strip()
        web_results = []
        search_query = message
        needs_web = query.needs_search or query.needs_time or query.needs_tools

        is_followup = any(w in msg_lower for w in FOLLOWUP_WORDS)
        if is_followup:
            last_msg = self._get_last_user_msg(working_mem)
            if last_msg and needs_web:
                search_query = last_msg

        if needs_web:
            if "hijri" in search_query.lower():
                search_query = f"tanggal hijriyah hari ini {now.day} {months_id[now.month-1]} {now.year}"
            elif not search_query.endswith(str(now.year)):
                search_query += f" {now.year}"
            yield "\n__STATUS__:🌐 Mencari di web...\n"
            web_results = await web_search.search(search_query, max_results=5)

        from app.db.database import async_session as _async_session
        from app.db.postgres import PostgresDB as _PostgresDB
        knowledge_ctx = ""
        try:
            async with _async_session() as _s:
                _db = _PostgresDB(_s)
                pinned = await _db.get_pinned_knowledge(user_id)
                if pinned:
                    lines = ["[PINNED NOTES]"]
                    for kb in pinned:
                        tag_str = f" #{' #'.join(kb.tags)}" if kb.tags else ""
                        lines.append(f"📌 {kb.title}{tag_str}")
                        if kb.content:
                            lines.append(f"   {kb.content[:200]}")
                    knowledge_ctx = "\n" + "\n".join(lines)
                if query.needs_search or query.needs_tools:
                    searched = await _db.search_knowledge(user_id, message, 3)
                    if searched:
                        lines = ["[KNOWLEDGE BASE]"]
                        for kb in searched:
                            lines.append(f"• {kb.title}: {kb.content[:200]}")
                        knowledge_ctx += "\n" + "\n".join(lines)
        except Exception:
            pass

        yield "\n__STATUS__:💭 Menulis respons...\n"

        date_str = f"hari {days[now.weekday()]}, {now.day} {months_id[now.month-1]} {now.year}"
        time_context = f"\n[CURRENT DATE] Sekarang {date_str}, jam {now.hour:02d}:{now.minute:02d} WIB."
        try:
            from hijri_converter import Gregorian as G
            h = G(now.year, now.month, now.day).to_hijri()
            ma = ["Muharram","Safar","Rabi'ul Awwal","Rabi'ul Akhir","Jumadil Awwal","Jumadil Akhir",
                  "Rajab","Sya'ban","Ramadhan","Syawwal","Dzulqa'dah","Dzulhijjah"]
            time_context += f"\n[HIJRI DATE] {h.day} {ma[h.month-1]} {h.year} H."
        except Exception:
            pass

        tone = self._detect_tone(message)
        custom_name = await self.memory.db.get_preferred_ai_name(user_id)
        system_ctx = self._get_system_prompt(query.category, tone) + time_context + knowledge_ctx
        if web_results:
            from app.tools.web_search import web_search as ws
            system_ctx += f"\n\n{ws.format_for_prompt(web_results, search_query)}"

        compiled_prompt = self.prompt_compiler.compile(
            system_context=system_ctx, user_profile=user_profile,
            relevant_memories=relevant_mem, recent_messages=working_mem,
            current_message=message, max_context_tokens=self._get_max_context(query.complexity),
            ai_name=custom_name,
        )

        model = self.model_override or await self.router.select_model(complexity=query.complexity, category=query.category)
        tier = self.router.MODEL_TIERS.get(query.category or query.complexity or "simple", self.router.MODEL_TIERS["simple"])
        fallback_model = tier.get("fallback", model)
        attempts = [model]
        if fallback_model and fallback_model != model:
            attempts.append(fallback_model)

        full_response = ""
        last_error = None
        for attempt_model in attempts:
            try:
                async for chunk in llm_gateway.stream(model=attempt_model, messages=compiled_prompt,
                                                      max_tokens=self._get_max_output(query.complexity)):
                    full_response += chunk
                    yield chunk
                last_error = None
                break
            except Exception as stream_err:
                last_error = stream_err
                logger.error(f"Streaming error with {attempt_model}: {stream_err}")
                if attempt_model == fallback_model:
                    break
                continue

        if last_error:
            if not full_response:
                yield f"\n❌ Terjadi kesalahan saat memproses: {last_error}\n"
            else:
                yield f"\n\n_(Streaming terputus: {last_error})_"

        cmds = re.findall(r'__CMD__:(\w+?):(.+)', full_response)
        cmd_result = None
        for cmd_type, cmd_val in cmds:
            cmd_result = await self._execute_cmd(cmd_type, cmd_val.strip(), user_id)

        clean_response = re.sub(r'__STATUS__:[^\n]*\n?|__CMD__:[^\n]*', '', full_response).strip()

        import re as _re
        txt = clean_response

        split_at = -1

        # 1. Cari marker eksplisit
        for m in ["Jawaban:", "Respon:", "Mulai respon.", "Jawab:", "Saya jawab:", "Saya mulai jawab:",
                   "Answer:", "Here is my response:", "Thus, response:", "Aku akan menjawab:",
                   "Saya akan menjawab:", "Saya akan mulai:", "Ini jawaban saya:", "Saya merespon:",
                   "Final answer:", "Result:", "Hasil:", "Conclusion:", "Kesimpulan:"]:
            idx = txt.rfind(m)
            if idx > split_at: split_at = idx + len(m)

        # 2. Cari pola "N.**" atau "N." yang merupakan awal jawaban
        if split_at == -1:
            m = _re.search(r'5\.\s+\*\*', txt)
            if m: split_at = m.start()
            if split_at == -1:
                m = _re.search(r'\d+\.\s+\*\*[A-Z]', txt)
                if m: split_at = m.start()

        # 3. Cari kalimat non-reasoning terakhir
        if split_at == -1 and len(txt) > 100:
            m = _re.search(r'(Cireng|Cara|Resep|Tips|Fungsi|Pengertian|Definisi|Contoh|Manfaat|Langkah)\b', txt)
            if m:
                lines = txt.split('\n')
                for i in range(len(lines) - 1, -1, -1):
                    if _re.search(r'(Cireng|Cara|Resep|Tips|Fungsi|Pengertian|Definisi|Contoh|Manfaat|Langkah)', lines[i]):
                        split_at = '\n'.join(lines[:i]).__len__() + 1 if i > 1 else -1
                        break

        # Fallback: cari kalimat terakhir yang diawali greeting
        if split_at == -1:
            m = _re.search(r'(?i)([.!?])\s*(Halo|Hai|Hi|Selamat|Sore|Alhamdulillah|Tentu|Ya|Oke|Ok|Baik|Kabar|Siap)\b', txt)
            if m and m.start() > len(txt) * 0.3:
                split_at = m.start(2)

        # Fallback: baris terakhir yang bukan kata reasoning
        if split_at == -1 and len(txt) > 200:
            sentences = _re.split(r'(?<=[.!?])\s+', txt)
            for i in range(len(sentences) - 1, -1, -1):
                s = sentences[i].strip()
                if len(s) > 15 and len(s) < 200:
                    first_word = s.split()[0] if s.split() else ""
                    if not _re.match(r'(The|We|I|My|This|It|To|But|So|Let|In|For|First|Second|Since|Because|However|Therefore|Thus|Note|Wait|Yes|No|Maybe|Actually|Basically)', first_word, _re.I):
                        split_at = len(' '.join(sentences[:i])) + 1
                        break

        # Fallback: ambil 40% terakhir
        if split_at == -1 and len(txt) > 300:
            split_at = int(len(txt) * 0.6)

        if 0 < split_at < len(txt):
            answer = txt[split_at:].strip().lstrip('"\'!.,;:? ')
            answer = _re.sub(r'^[^a-zA-Z0-9]+', '', answer)
            if len(answer) > 20:
                yield f"\n__STRIPPED__:{answer}\n"
                clean_response = answer

        if cmd_result:
            clean_response += f"\n\n{cmd_result}"

        asyncio.create_task(self._post_process(user_id, conversation_id, message, clean_response, query))

    async def _handle_memory_command(self, user_id: str, message: str) -> str | None:
        msg_lower = message.lower().strip()
        for cmd, pattern in MEMORY_COMMANDS.items():
            match = re.match(pattern, msg_lower)
            if not match:
                continue
            from app.db.database import async_session
            from app.db.postgres import PostgresDB
            from app.llm.embeddings import Embedder
            content = match.group(1).strip()
            if not content:
                continue
            async with async_session() as session:
                db = PostgresDB(session)
                embedder = Embedder()
                memory = MemoryManager(db, embedder)
                user = await db.get_user(user_id)
                if not user:
                    from app.db.models import User as UserModel
                    from sqlalchemy import insert
                    await session.execute(insert(UserModel).values(id=user_id, username=user_id))
                    await session.commit()
                if cmd == "ganti_namamu":
                    await db.set_preferred_ai_name(user_id, content)
                    return f"✅ Oke, panggil aku *{content}* mulai sekarang!"
                elif cmd == "ganti_namaku":
                    profile = await db.get_user_profile(user_id)
                    profile["name"] = content
                    await db.update_user_profile(user_id, profile)
                    return f"✅ Senang kenal, *{content}*!"
                elif cmd == "ingat":
                    words = content.split()
                    skip = {"aku", "saya", "my", "i"}
                    key = words[1] if len(words) >= 2 and words[0] in skip else words[0] if words else "catatan"
                    existing = await db.find_fact(user_id, "personal", key)
                    if existing:
                        await db.update_fact(existing.id, content)
                        from app.db.vector_store import vector_store
                        await vector_store.delete(existing.id)
                        embed = await embedder.embed(f"{key}: {content}")
                        await vector_store.upsert("user_memories", existing.id, embed, {
                            "id": existing.id, "user_id": user_id, "fact_type": "personal",
                            "content": f"{key}: {content}", "decay_score": 1.0, "access_count": 0,
                        })
                        return f"✅ Diperbaharui! *{content}*"
                    else:
                        await memory.long_term.store_fact(user_id, None, {"type": "personal", "key": key, "value": content})
                        return f"✅ Disimpan! *{content}*"
                elif cmd == "update":
                    existing = await db.get_user_facts(user_id)
                    if not existing:
                        return "📭 Belum ada."
                    for f in existing:
                        if content.lower() in f.fact_key.lower() or content.lower() in f.fact_value.lower():
                            val = content.split("menjadi")[-1].strip() if "menjadi" in content else content
                            await db.update_fact(f.id, val)
                            from app.db.vector_store import vector_store
                            await vector_store.delete(f.id)
                            embed = await embedder.embed(f"{f.fact_key}: {val}")
                            await vector_store.upsert("user_memories", f.id, embed, {
                                "id": f.id, "user_id": user_id, "fact_type": f.fact_type,
                                "content": f"{f.fact_key}: {val}", "decay_score": 1.0, "access_count": 0,
                            })
                            return f"✅ Diperbaharui: *{f.fact_key}: {val}*"
                    return f"🔍 Tidak nemu *{content}*"
                elif cmd == "lupa":
                    facts = await db.get_user_facts(user_id)
                    for f in facts:
                        if content.lower() in f.fact_value.lower() or content.lower() in f.fact_key.lower():
                            await db.delete_fact(f.id)
                            from app.db.vector_store import vector_store
                            await vector_store.delete(f.id)
                            return f"🗑️ Dihapus! *{f.fact_key}: {f.fact_value}*"
                    return f"🔍 Tidak nemu *{content}*"
        for cmd, pattern in KNOWLEDGE_COMMANDS.items():
            match = re.match(pattern, msg_lower)
            if not match:
                continue
            content = match.group(1).strip()
            if not content:
                continue
            from app.db.database import async_session
            from app.db.postgres import PostgresDB
            async with async_session() as session:
                db = PostgresDB(session)
                user = await db.get_user(user_id)
                if not user:
                    from app.db.models import User as UserModel
                    from sqlalchemy import insert
                    await session.execute(insert(UserModel).values(id=user_id, username=user_id))
                    await session.commit()
                if cmd == "simpan":
                    parts = content.split("\n", 1)
                    title = parts[0].strip()[:200]
                    body = parts[1].strip() if len(parts) > 1 else ""
                    if not body:
                        body = title
                        title = title[:60]
                    tags = []
                    try:
                        tag_prompt = f"Extract 1-3 tags from this text. Return ONLY comma-separated words. Text: {title}"
                        tag_result = await llm_gateway.complete(model="google/gemini-2.0-flash-exp:free", prompt=tag_prompt, max_tokens=30)
                        tags = [t.strip().lower() for t in tag_result.split(",") if t.strip() and len(t.strip()) < 20]
                    except Exception:
                        pass
                    kb = await db.create_knowledge(user_id, title, body, tags=tags[:3], source="chat")
                    tag_str = f" #{' #'.join(kb.tags)}" if kb.tags else ""
                    return f"✅ Catatan disimpan: *{kb.title}*{tag_str}"
                elif cmd == "cari_catatan":
                    results = await db.search_knowledge(user_id, content, 3)
                    if not results:
                        return f"🔍 Tidak nemu catatan tentang *{content}*"
                    lines = [f"📚 Catatan ditemukan:"]
                    for kb in results:
                        tag_str = f" #{' #'.join(kb.tags)}" if kb.tags else ""
                        flag = " 📌" if kb.is_pinned else ""
                        lines.append(f"• *{kb.title}*{flag}{tag_str}")
                        if kb.content:
                            lines.append(f"  {kb.content[:150]}")
                    return "\n".join(lines)
        return None

    async def _post_process(self, user_id: str, conversation_id: str, user_msg: str, ai_response: str, query):
        from app.db.database import async_session
        from app.db.postgres import PostgresDB
        from sqlalchemy import update
        from app.db.models import Conversation as ConvModel
        async with async_session() as session:
            db = PostgresDB(session)
            conv = await db.get_conversation(conversation_id)
            if not conv:
                c = ConvModel(id=conversation_id, user_id=user_id, category=query.category)
                c.title = user_msg[:60] + ".." if len(user_msg) > 60 else user_msg[:60]
                session.add(c)
                await session.commit()
            elif not conv.title:
                title = user_msg[:60] + ".." if len(user_msg) > 60 else user_msg
                await session.execute(update(ConvModel).where(ConvModel.id == conv.id).values(title=title))
                await session.commit()
            memory = MemoryManager(db, self.memory.long_term.embedder)
            await memory.save_messages(conversation_id, user_msg, ai_response)
            await memory.update_working_memory(user_id, conversation_id, user_msg, ai_response)
            await memory.extract_and_store_facts(user_id, conversation_id, user_msg, ai_response)
            await memory.compress_if_needed(user_id, conversation_id)
            await redis_client.store_response(user_msg, user_id, ai_response)

    def _get_system_prompt(self, category: str, tone: str = "neutral") -> str:
        base = self.prompt_compiler.SYSTEM_PROMPTS.get(category, self.prompt_compiler.SYSTEM_PROMPTS["default"])
        tone_map = {
            "sympathetic": "\n\nTONE: User seems sad or struggling. Respond with extra warmth and empathy.",
            "calm": "\n\nTONE: User seems upset. Stay calm, don't be defensive, be understanding.",
            "cheerful": "\n\nTONE: User is cheerful! Match their positive energy and enthusiasm.",
            "anxious": "\n\nTONE: User seems anxious or worried. Reassure them, be calm and supportive.",
            "tired": "\n\nTONE: User seems tired or low energy. Be gentle, don't push too much.",
        }
        return base + tone_map.get(tone, "")

    def _get_max_context(self, complexity: str) -> int:
        return {"simple": 500, "moderate": 2000, "complex": 4000}.get(complexity, 2000)

    def _get_max_output(self, complexity: str) -> int:
        return {"simple": 300, "moderate": 1000, "complex": 4000}.get(complexity, 1000)
