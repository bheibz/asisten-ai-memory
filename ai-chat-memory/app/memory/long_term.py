from uuid import uuid4
from datetime import datetime

from app.db.postgres import PostgresDB
from app.db.vector_store import vector_store


class LongTermMemory:

    def __init__(self, db: PostgresDB, embedder):
        self.db = db
        self.embedder = embedder

    async def retrieve(self, user_id: str, query: str, top_k: int = 5) -> list[dict]:
        query_embedding = await self.embedder.embed(query)
        results = await vector_store.search(
            collection="user_memories",
            vector=query_embedding,
            filter_condition={"user_id": user_id, "decay_score": {"$gt": 0.3}},
            top_k=top_k,
            query_text=query,
        )
        for r in results:
            await self._boost_memory(r["id"])
        return [
            {"content": r["content"], "relevance": r["score"]}
            for r in results if r["score"] > 0
        ]

    async def retrieve_all(self, user_id: str) -> list[dict]:
        from app.db.models import MemoryFact
        from sqlalchemy import select
        result = await self.db.session.execute(
            select(MemoryFact).where(MemoryFact.user_id == user_id, MemoryFact.decay_score > 0.3)
            .order_by(MemoryFact.decay_score.desc()).limit(10)
        )
        facts = result.scalars().all()
        return [{"content": f"{f.fact_key}: {f.fact_value}", "relevance": 0.5} for f in facts]

    async def store_fact(self, user_id: str, conv_id: str, fact: dict):
        embedding = await self.embedder.embed(f"{fact['key']}: {fact['value']}")
        point_id = str(uuid4())
        await vector_store.upsert(
            collection="user_memories",
            point_id=point_id,
            vector=embedding,
            payload={
                "id": point_id,
                "user_id": user_id,
                "fact_type": fact.get("type", "knowledge"),
                "content": f"{fact['key']}: {fact['value']}",
                "source_conversation_id": conv_id,
                "created_at": datetime.now().isoformat(),
                "decay_score": 1.0,
                "access_count": 0,
            },
        )
        await self.db.insert_fact(user_id, conv_id, fact)

    async def _boost_memory(self, point_id: str):
        try:
            from app.db.models import MemoryFact
            from sqlalchemy import select, update
            async with self.db.session as session:
                result = await session.execute(select(MemoryFact).where(MemoryFact.id == point_id))
                fact = result.scalar_one_or_none()
                if fact:
                    await session.execute(
                        update(MemoryFact).where(MemoryFact.id == point_id).values(
                            access_count=MemoryFact.access_count + 1,
                            last_accessed=datetime.now(),
                            decay_score=min(1.0, fact.decay_score + 0.1),
                        )
                    )
                    await session.commit()
        except Exception:
            pass
