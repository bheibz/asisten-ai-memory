import asyncio
from app.config import settings
from app.db.postgres import PostgresDB
from app.db.redis_client import redis_client
from app.db.vector_store import vector_store
from app.memory.working_memory import WorkingMemory
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.compressor import Compressor
from app.memory.fact_extractor import FactExtractor
from app.memory.decay_engine import DecayEngine


class MemoryManager:

    def __init__(self, db: PostgresDB, embedder):
        self.db = db
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory(db)
        self.long_term = LongTermMemory(db, embedder)
        self.compressor = Compressor()
        self.fact_extractor = FactExtractor()
        self.decay = DecayEngine(db)

    async def get_working_memory(self, user_id: str, conv_id: str, limit: int = 5) -> list[dict]:
        return await self.working.get(user_id, conv_id, limit)

    async def update_working_memory(self, user_id: str, conv_id: str, user_msg: str, ai_response: str):
        await self.working.update(user_id, conv_id, user_msg, ai_response)

    async def retrieve_relevant(self, user_id: str, query: str, top_k: int = 5) -> list[dict]:
        if not query.strip():
            return []
        results = await self.long_term.retrieve(user_id, query, top_k)
        if not results:
            results = await self.long_term.retrieve_all(user_id)
        return results[:top_k]

    async def get_user_profile(self, user_id: str) -> dict:
        return await self.db.get_user_profile(user_id) or {}

    async def save_messages(self, conv_id: str, user_msg: str, ai_response: str):
        await self.db.save_message(conv_id, "user", user_msg)
        await self.db.save_message(conv_id, "assistant", ai_response)

    async def extract_and_store_facts(self, user_id: str, conv_id: str, user_msg: str, ai_response: str):
        facts = await self.fact_extractor.extract(user_msg, ai_response)
        for fact in facts:
            existing = await self.db.find_fact(user_id, fact.get("type", "knowledge"), fact.get("key", ""))
            if existing:
                await self.db.update_fact(existing.id, fact["value"])
            else:
                await self.long_term.store_fact(user_id, conv_id, fact)

    async def compress_if_needed(self, user_id: str, conv_id: str):
        await self.short_term.compress_if_needed(user_id, conv_id, self.compressor)
