"""
Brain orchestrator — main chat pipeline.
Delegates to:
- CommandHandler   → user command detection & execution
- ContextBuilder   → time/date/knowledge/tone context
- ResponseCleaner  → strip reasoning noise from output
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from app.core.query_classifier import QueryClassifier, ProcessedQuery as QueryResult
from app.core.prompt_compiler import PromptCompiler
from app.core.model_router import ModelRouter, MODEL_POOLS
from app.core.command_handler import CommandHandler
from app.core.context_builder import ContextBuilder
from app.core.response_cleaner import ResponseCleaner
from app.memory.memory_manager import MemoryManager
from app.llm.gateway import llm_gateway
from app.db.redis_client import redis_client
from app.tools.web_search import web_search

logger = logging.getLogger(__name__)

# ── Follow-up detection ─────────────────────────────────────────────────

_FOLLOWUP_WORDS = frozenset({
    "terus", "lanjut", "detail", "jelasin", "jelaskan",
    "lebih", "coba lagi", "cari", "cek", "lagi",
})

_DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


class BrainOrchestrator:
    """Main chat pipeline: classify → detect command → retrieve memory → build context → stream."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
        self.classifier = QueryClassifier()
        self.prompt_compiler = PromptCompiler()
        self.router = ModelRouter(llm_gateway=llm_gateway)
        self.model_override: Optional[str] = None
        self.cleaner = ResponseCleaner()

    # ── Public API ──────────────────────────────────────────────────────

    async def process_message(
        self, user_id: str, conversation_id: str, message: str,
    ) -> AsyncGenerator[str, None]:
        """Main entry point: process a user message and stream the response."""
        try:
            async for chunk in self._process_impl(user_id, conversation_id, message):
                yield chunk
        except Exception as e:
            logger.exception(f"Fatal error in process_message: {e}")
            yield f"\n❌ Terjadi kesalahan internal: {e}\n"

    async def _process_impl(
        self, user_id: str, conversation_id: str, message: str,
    ) -> AsyncGenerator[str, None]:

        # 1. Detect & handle user commands
        cmd_handler = CommandHandler(self.memory.db)
        cmd_result = await cmd_handler.handle(user_id, message)
        if cmd_result:
            yield cmd_result
            return

        # 2. Check response cache
        cached = await redis_client.get_response(message, user_id)
        if cached:
            yield cached
            return

        # 3. Classify query
        query = await self.classifier.classify(message)

        # 4. Retrieve memory
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

        # 5. Web search (if needed)
        needs_web = query.needs_search or query.needs_time or query.needs_tools
        if needs_web:
            yield "\n__STATUS__:🌐 Mencari di web...\n"
        web_results, search_query = await self._maybe_search(
            message, query, working_mem,
        )

        # 6. Build context
        system_ctx = await self._build_context(
            user_id=user_id, message=message, query=query,
            web_results=web_results, search_query=search_query,
        )

        # 7. Compile prompt
        custom_name = await self.memory.db.get_preferred_ai_name(user_id)
        compiled_prompt = self.prompt_compiler.compile(
            system_context=system_ctx, user_profile=user_profile,
            relevant_memories=relevant_mem, recent_messages=working_mem,
            current_message=message,
            max_context_tokens=self._get_max_context(query.complexity),
            ai_name=custom_name,
        )

        # 8. Select model & stream with multi-provider pool + backoff
        import asyncio
        tier_key = query.category or query.complexity or "simple"

        if self.model_override:
            # User specified a model — respect it, try once
            model_pool = [self.model_override]
        else:
            model_pool = self._get_model_pool(tier_key)

        full_response = ""
        last_error = None
        tried = set()

        for i, attempt_model in enumerate(model_pool):
            if attempt_model in tried:
                continue
            tried.add(attempt_model)

            try:
                async for chunk in llm_gateway.stream(
                    model=attempt_model, messages=compiled_prompt,
                    max_tokens=self._get_max_output(query.complexity),
                ):
                    full_response += chunk
                    yield chunk
                # Success — reset breaker
                await self.router.on_success(attempt_model)
                last_error = None
                break
            except Exception as stream_err:
                last_error = stream_err
                delay = await self.router.on_error(attempt_model, stream_err)
                logger.warning(
                    f"Streaming error with {attempt_model}: {stream_err} "
                    f"(retry delay: {delay}s)"
                )
                if delay and delay > 0:
                    await asyncio.sleep(delay)

        # 9. Handle errors
        if last_error:
            if not full_response:
                yield f"\n❌ Terjadi kesalahan saat memproses: {last_error}\n"
                return
            else:
                yield f"\n\n_(Streaming terputus: {last_error})_"

        # 10. Clean & strip reasoning noise
        cleaned = self.cleaner.clean(full_response)
        if cleaned and cleaned != full_response:
            yield f"\n__STRIPPED__:{cleaned}\n"

        # 11. Post-process (async background with error logging)
        asyncio.create_task(
            self._post_process(user_id, conversation_id, message, cleaned or full_response, query),
            name=f"postprocess-{user_id}-{conversation_id}",
        )

    # ── Web search ──────────────────────────────────────────────────────

    async def _maybe_search(self, message: str, query: QueryResult,
                            working_mem: list) -> tuple[list, str]:
        """Perform web search if query needs it. Returns (results, effective_query)."""
        web_results = []
        search_query = message
        needs_web = query.needs_search or query.needs_time or query.needs_tools

        if not needs_web:
            return [], search_query

        # Follow-up detection — use previous context
        msg_lower = message.lower().strip()
        if any(w in msg_lower for w in _FOLLOWUP_WORDS):
            last_msg = self._get_last_user_msg(working_mem)
            if last_msg:
                search_query = last_msg

        now = datetime.now()
        if "hijri" in search_query.lower():
            search_query = (
                f"tanggal hijriyah hari ini {now.day} "
                f"{_MONTHS_ID[now.month - 1]} {now.year}"
            )
        elif not search_query.endswith(str(now.year)):
            search_query += f" {now.year}"

        web_results = await web_search.search(search_query, max_results=5)
        return web_results, search_query

    # ── Context building ────────────────────────────────────────────────

    async def _build_context(self, user_id: str, message: str,
                              query: QueryResult, web_results: list,
                              search_query: str) -> str:
        """Build full system context."""
        tone = ContextBuilder.detect_tone(message)
        time_ctx = ContextBuilder.build_time_context()
        knowledge_ctx = await ContextBuilder.build_knowledge_context(
            user_id, query.needs_search or query.needs_tools, message,
        )
        system_prompt = ContextBuilder.get_system_prompt(query.category, tone)
        system_ctx = system_prompt + time_ctx + knowledge_ctx

        if web_results:
            system_ctx += f"\n\n{web_search.format_for_prompt(web_results, search_query)}"

        return system_ctx

    # ── Post-processing ─────────────────────────────────────────────────

    async def _post_process(self, user_id: str, conversation_id: str,
                             user_msg: str, ai_response: str, query):
        """Save messages, update memory, extract facts (async background).
        Errors are logged but never raised — this is fire-and-forget."""
        try:
            await self._do_post_process(user_id, conversation_id, user_msg, ai_response, query)
        except Exception as e:
            logger.error(f"Post-process failed for {user_id}/{conversation_id}: {e}")

    async def _do_post_process(self, user_id: str, conversation_id: str,
                                user_msg: str, ai_response: str, query):
        """Save messages, update memory, extract facts (async background)."""
        from app.db.database import async_session
        from app.db.postgres import PostgresDB
        from sqlalchemy import update
        from app.db.models import Conversation as ConvModel

        async with async_session() as session:
            db = PostgresDB(session)

            # Ensure conversation exists
            conv = await db.get_conversation(conversation_id)
            if not conv:
                c = ConvModel(
                    id=conversation_id, user_id=user_id,
                    category=getattr(query, 'category', None),
                )
                c.title = user_msg[:60] + ".." if len(user_msg) > 60 else user_msg[:60]
                session.add(c)
                await session.commit()
            elif not conv.title:
                title = user_msg[:60] + ".." if len(user_msg) > 60 else user_msg
                await session.execute(
                    update(ConvModel).where(ConvModel.id == conv.id).values(title=title)
                )
                await session.commit()

            memory = MemoryManager(db, self.memory.long_term.embedder)
            await memory.save_messages(conversation_id, user_msg, ai_response)
            await memory.update_working_memory(user_id, conversation_id, user_msg, ai_response)
            await memory.extract_and_store_facts(user_id, conversation_id, user_msg, ai_response)
            await memory.compress_if_needed(user_id, conversation_id)
            await redis_client.store_response(user_msg, user_id, ai_response)

    @staticmethod
    def _get_model_pool(tier_key: str) -> list[str]:
        """Get the full model pool for a tier, with fallbacks."""
        pool = MODEL_POOLS.get(tier_key, MODEL_POOLS["simple"])
        # Make a copy so we don't mutate the global
        return list(pool)

    @staticmethod
    def _get_last_user_msg(working_mem: list) -> str:
        for m in reversed(working_mem):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

    @staticmethod
    def _get_max_context(complexity: str) -> int:
        return {"simple": 500, "moderate": 2000, "complex": 4000}.get(
            complexity, 2000)

    @staticmethod
    def _get_max_output(complexity: str) -> int:
        return {"simple": 300, "moderate": 1000, "complex": 4000}.get(
            complexity, 1000)
