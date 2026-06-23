from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.postgres import PostgresDB, get_session
from app.db.vector_store import vector_store

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class TeachRequest(BaseModel):
    type: str = "knowledge"
    key: str
    value: str


@router.get("/{user_id}")
async def get_user_memory(user_id: str, db: PostgresDB = Depends(get_session)):
    facts = await db.get_user_facts(user_id)
    return [
        {
            "id": str(f.id),
            "type": f.fact_type,
            "key": f.fact_key,
            "value": f.fact_value,
            "confidence": f.confidence,
            "decay_score": f.decay_score,
        }
        for f in facts
    ]


@router.delete("/{user_id}/{fact_id}")
async def forget_fact(user_id: str, fact_id: str, db: PostgresDB = Depends(get_session)):
    await db.delete_fact(fact_id)
    await vector_store.delete(fact_id)
    return {"status": "forgotten", "fact_id": fact_id}


@router.post("/{user_id}/teach")
async def teach_memory(user_id: str, fact: TeachRequest, db: PostgresDB = Depends(get_session)):
    from uuid import uuid4
    from app.llm.embeddings import Embedder
    embedder = Embedder()
    embedding = await embedder.embed(f"{fact.key}: {fact.value}")
    point_id = str(uuid4())
    await vector_store.upsert(
        collection="user_memories",
        point_id=point_id,
        vector=embedding,
        payload={
            "id": point_id,
            "user_id": user_id,
            "fact_type": fact.type,
            "content": f"{fact.key}: {fact.value}",
            "decay_score": 1.0,
            "access_count": 0,
        },
    )
    await db.insert_fact(user_id, None, {"type": fact.type, "key": fact.key, "value": fact.value})
    return {"status": "learned", "fact_id": point_id}
