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


class BrainOrchestrator:

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.classifier = QueryClassifier()
        self.prompt_compiler = PromptCompiler()
        self.router = ModelRouter()

    async def process_message(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
    ) -> AsyncGenerator[str, None]:
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

        web_results = []
        if query.needs_tools:
            yield "\n__STATUS__:🌐 Mencari di web...\n"
            web_results = await web_search.search(message, max_results=5)

        yield "\n__STATUS__:💭 Menulis respons...\n"

        from datetime import datetime
        time_context = ""
        if query.needs_time:
            now = datetime.now()
            days = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
            months = ["Januari","Februari","Maret","April","Mei","Juni",
                      "Juli","Agustus","September","Oktober","November","Desember"]
            time_context = f"\n[CURRENT DATE] Sekarang hari {days[now.weekday()]}, {now.day} {months[now.month-1]} {now.year}, jam {now.hour:02d}:{now.minute:02d} WIB."

        custom_name = user_profile.get("ai_name") if user_profile else None
        compiled_prompt = self.prompt_compiler.compile(
            system_context=self._get_system_prompt(query.category) + time_context,
            user_profile=user_profile,
            relevant_memories=relevant_mem,
            recent_messages=working_mem,
            current_message=message,
            max_context_tokens=self._get_max_context(query.complexity),
            web_results=web_results,
            ai_name=custom_name,
        )

        model = self.router.select_model(
            complexity=query.complexity,
            category=query.category,
            token_budget=10000,
        )

        import re as _re
        full_response = ""
        async for chunk in llm_gateway.stream(
            model=model,
            messages=compiled_prompt,
            max_tokens=self._get_max_output(query.complexity),
        ):
            full_response += chunk
            yield chunk

        clean_response = _re.sub(r'__STATUS__:[^\n]*\n?', '', full_response).strip()
        asyncio.create_task(
            self._post_process(user_id, conversation_id, message, clean_response, query)
        )

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
                    user = await db.get_user(user_id)

                if cmd == "ingat":
                    words = content.split()
                    skip = {"aku", "saya", "my", "i", "gue", "gw", "kami", "kita"}
                    key = "catatan"
                    if len(words) >= 2:
                        key = words[1] if words[0] in skip else words[0]
                    elif len(words) == 1:
                        key = words[0]
                    val = content
                    existing = await db.find_fact(user_id, "personal", key)
                    if existing:
                        await db.update_fact(existing.id, val)
                        from app.db.vector_store import vector_store
                        await vector_store.delete(existing.id)
                        embed = await embedder.embed(f"{key}: {val}")
                        await vector_store.upsert("user_memories", existing.id, embed, {
                            "id": existing.id, "user_id": user_id, "fact_type": "personal",
                            "content": f"{key}: {val}", "decay_score": 1.0, "access_count": 0,
                        })
                        return f"✅ Diperbaharui! {key}: *{val}*"
                    else:
                        fact = {"type": "personal", "key": key, "value": val}
                        await memory.long_term.store_fact(user_id, None, fact)
                        return f"✅ Disimpan! {key}: *{val}*"

                elif cmd == "update":
                    existing = await db.get_user_facts(user_id)
                    if not existing:
                        return f"📭 Belum ada memory untuk diperbaharui."
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
                            return f"✅ Memory diperbaharui: *{f.fact_key}: {val}*"
                    return f"🔍 Tidak nemu memory tentang *{content}*"

                elif cmd == "ganti_namamu":
                    profile = await db.get_user_profile(user_id)
                    profile["ai_name"] = content
                    await db.update_user_profile(user_id, profile)
                    return f"✅ Oke, panggil aku *{content}* mulai sekarang!"

                elif cmd == "ganti_namaku":
                    profile = await db.get_user_profile(user_id)
                    profile["name"] = content
                    await db.update_user_profile(user_id, profile)
                    return f"✅ Senang kenal, *{content}*! Aku akan ingat namamu."

                elif cmd == "lupa":
                    facts = await db.get_user_facts(user_id)
                    for f in facts:
                        if content.lower() in f.fact_value.lower() or content.lower() in f.fact_key.lower():
                            await db.delete_fact(f.id)
                            from app.db.vector_store import vector_store
                            await vector_store.delete(f.id)
                            return f"🗑️ Dihapus! {f.fact_key}: *{f.fact_value}*"
                    return f"🔍 Tidak nemu memory tentang *{content}*"

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
                from app.utils.helpers import generate_id
                cid = conversation_id
                c = ConvModel(id=cid, user_id=user_id, category=query.category)
                c.title = (user_msg[:60] + "..") if len(user_msg) > 60 else user_msg[:60]
                session.add(c)
                await session.commit()
            elif not conv.title:
                title = (user_msg[:60] + "..") if len(user_msg) > 60 else user_msg
                await session.execute(update(ConvModel).where(ConvModel.id == conv.id).values(title=title))
                await session.commit()
            memory = MemoryManager(db, self.memory.long_term.embedder)
            await memory.save_messages(conversation_id, user_msg, ai_response)
            await memory.update_working_memory(user_id, conversation_id, user_msg, ai_response)
            await memory.extract_and_store_facts(user_id, conversation_id, user_msg, ai_response)
            await memory.compress_if_needed(user_id, conversation_id)
            await redis_client.store_response(user_msg, user_id, ai_response)

    def _get_system_prompt(self, category: str) -> str:
        return self.prompt_compiler.SYSTEM_PROMPTS.get(category, self.prompt_compiler.SYSTEM_PROMPTS["default"])

    def _get_max_context(self, complexity: str) -> int:
        return {"simple": 500, "moderate": 2000, "complex": 4000}.get(complexity, 2000)

    def _get_max_output(self, complexity: str) -> int:
        return {"simple": 300, "moderate": 1000, "complex": 4000}.get(complexity, 1000)
