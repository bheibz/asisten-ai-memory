from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.postgres import PostgresDB, get_session

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


class KnowledgeCreate(BaseModel):
    title: str
    content: str
    tags: list = []
    source: str = "chat"
    is_pinned: bool = False


@router.post("/knowledge/{user_id}")
async def create_knowledge(user_id: str, body: KnowledgeCreate, db: PostgresDB = Depends(get_session)):
    kb = await db.create_knowledge(user_id, body.title, body.content, body.tags, body.source, body.is_pinned)
    return {"id": kb.id, "title": kb.title, "tags": kb.tags}


@router.get("/knowledge/{user_id}")
async def list_knowledge(user_id: str, q: str = "", limit: int = 50, db: PostgresDB = Depends(get_session)):
    if q:
        items = await db.search_knowledge(user_id, q, limit)
    else:
        items = await db.get_knowledge(user_id, limit)
    return [
        {"id": kb.id, "title": kb.title, "content": kb.content[:200], "tags": kb.tags,
         "source": kb.source, "is_pinned": kb.is_pinned, "created_at": kb.created_at.isoformat()}
        for kb in items
    ]


@router.delete("/knowledge/{kb_id}")
async def delete_knowledge(kb_id: str, db: PostgresDB = Depends(get_session)):
    await db.delete_knowledge(kb_id)
    return {"status": "deleted"}


@router.put("/knowledge/{kb_id}/pin")
async def toggle_pin(kb_id: str, db: PostgresDB = Depends(get_session)):
    await db.toggle_pin_knowledge(kb_id)
    return {"status": "toggled"}


@router.get("/knowledge/{user_id}/stats")
async def knowledge_stats(user_id: str, db: PostgresDB = Depends(get_session)):
    items = await db.get_knowledge(user_id, 1000)
    all_tags = []
    for kb in items:
        all_tags.extend(kb.tags or [])
    from collections import Counter
    tag_counts = dict(Counter(all_tags).most_common(10))
    return {"total": len(items), "pinned": sum(1 for kb in items if kb.is_pinned), "tags": tag_counts}
