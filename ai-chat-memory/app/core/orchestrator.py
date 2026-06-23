import asyncio
import re
from typing import AsyncGenerator

from app.core.query_classifier import QueryClassifier
from app.core.prompt_compiler import PromptCompiler
from app.core.model_router import ModelRouter
from app.memory.memory_manager import MemoryManager
from app.llm.gateway import llm_gateway
from app.db.redis_client import redis_client
from app.tools.web_search import web_search

MEMORY_COMMANDS = {
    "ganti_namamu": r"(?:aku\s+)?(?:ganti|ubah|set|panggil)\s+(?:(?:nama\s+)?kamu|namamu)\s+(?:menjadi|jadi|:)?\s*([a-zA-Z0-9_]+)",
    "ganti_namaku": r"(?:aku\s+)?(?:ganti|ubah|set|panggil)\s+(?:(?:nama\s+)?(?:aku|saya)|namaku)\s+(?:menjadi|jadi|:)?\s*([a-zA-Z0-9_]+)",
    "ingat": r"(?:ingat|catat|simpan|remember|save|note)\s+(?:bahwa|:|\s)?\s*(.+)",
    "lupa": r"(?:lupa|forget|hapus|delete|remove)\s+(?:bahwa|:|\s)?\s*(.+)",
    "update": r"(?:perbaharui|ubah|update|ganti|edit|change)\s+(?:catatan|memory|memori|note)?\s*(?:tentang|mengenai|:)?\s*(.+)",
}

FOLLOWUP_WORDS = {"terus", "lanjut", "detail", "jelasin", "jelaskan", "lebih", "coba lagi"}
FAIL_PATTERNS = ["maaf", "tidak bisa", "tidak tahu", "sorry", "can't", "cannot", "tidak memiliki akses"]
SAD_WORDS = {"sedih", "kecewa", "sakit", "lelah", "sendiri", "betah", "pusing"}
ANGRY_WORDS = {"marah", "kesal", "sebal", "geram", "jengkel"}
HAPPY_WORDS = {"senang", "bahagia", "syukur", "ceria", "happy", "seneng"}


class BrainOrchestrator:

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.classifier = QueryClassifier()
        self.prompt_compiler = PromptCompiler()
        self.router = ModelRouter()

    def _get_last_user_msg(self, working_mem: list) -> str:
        for m in reversed(working_mem):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

    def _detect_tone(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in SAD_WORDS): return "sympathetic"
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
                profile = await db.get_user_profile(user_id)
                profile["ai_name"] = cmd_val
                await db.update_user_profile(user_id, profile)
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

        from datetime import datetime
        now = datetime.now()
        days = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
        months_id = ["Januari","Februari","Maret","April","Mei","Juni",
                     "Juli","Agustus","September","Oktober","November","Desember"]

        msg_lower = message.lower().strip()
        force_smart = query.needs_search or query.needs_time
        web_results = []
        search_query = message

        # Smart follow-up
        is_followup = any(w in msg_lower for w in FOLLOWUP_WORDS or bool(re.search(r"cek (di|ke)\s+(internet|online|web|google)", msg_lower)))
        if is_followup:
            last_msg = self._get_last_user_msg(working_mem)
            if last_msg:
                search_query = last_msg
                force_smart = True

        if force_smart:
            if "hijri" in search_query.lower():
                search_query = f"tanggal hijriyah hari ini {now.day} {months_id[now.month-1]} {now.year}"
            elif not search_query.endswith(str(now.year)):
                search_query += f" {now.year}"
            yield "\n__STATUS__:🌐 Mencari di web...\n"
            web_results = await web_search.search(search_query, max_results=5)

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
        custom_name = user_profile.get("ai_name") if user_profile else None
        system_ctx = self._get_system_prompt(query.category, tone) + time_context
        if web_results:
            from app.tools.web_search import web_search as ws
            system_ctx += f"\n\n{ws.format_for_prompt(web_results, search_query)}"

        compiled_prompt = self.prompt_compiler.compile(
            system_context=system_ctx, user_profile=user_profile,
            relevant_memories=relevant_mem, recent_messages=working_mem,
            current_message=message, max_context_tokens=self._get_max_context(query.complexity),
            ai_name=custom_name,
        )

        model = self.router.select_model(complexity=query.complexity, category=query.category,
                                         token_budget=10000, force_smart=force_smart)

        full_response = ""
        async for chunk in llm_gateway.stream(model=model, messages=compiled_prompt,
                                              max_tokens=self._get_max_output(query.complexity)):
            full_response += chunk
            yield chunk

        # __CMD__: execution + auto-retry
        cmds = re.findall(r'__CMD__:(\w+?):(.+)', full_response)
        cmd_result = None
        for cmd_type, cmd_val in cmds:
            cmd_result = await self._execute_cmd(cmd_type, cmd_val.strip(), user_id)

        clean_response = re.sub(r'__STATUS__:[^\n]*\n?|__CMD__:[^\n]*', '', full_response).strip()

        # Auto-retry: if north-mini fails and response is short+negative
        is_failure = any(p in clean_response.lower() for p in FAIL_PATTERNS)
        if not force_smart and is_failure and len(clean_response.split()) < 40:
            yield "\n\n__STATUS__:🔄 Mencoba dengan model lebih besar...\n"
            smart_prompt = self.prompt_compiler.compile(
                system_context="Answer accurately and concisely. Use web search results if available." + time_context,
                user_profile=user_profile, relevant_memories=relevant_mem,
                recent_messages=working_mem, current_message=message,
                max_context_tokens=2000, ai_name=custom_name,
            )
            retry_response = ""
            async for chunk in llm_gateway.stream(model="oc/deepseek-v4-flash-free", messages=smart_prompt,
                                                  max_tokens=1000):
                retry_response += chunk
                yield chunk
            clean_response = retry_response

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
                    profile = await db.get_user_profile(user_id)
                    profile["ai_name"] = content
                    await db.update_user_profile(user_id, profile)
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
        }
        return base + tone_map.get(tone, "")

    def _get_max_context(self, complexity: str) -> int:
        return {"simple": 500, "moderate": 2000, "complex": 4000}.get(complexity, 2000)

    def _get_max_output(self, complexity: str) -> int:
        return {"simple": 300, "moderate": 1000, "complex": 4000}.get(complexity, 1000)
