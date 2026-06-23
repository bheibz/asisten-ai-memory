from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db.database import async_session
from app.db.postgres import PostgresDB, get_session
from app.llm.embeddings import Embedder
from app.memory.memory_manager import MemoryManager
from app.core.orchestrator import BrainOrchestrator

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    conversation_id: str
    message: str


def make_orchestrator(db: PostgresDB):
    embedder = Embedder()
    return BrainOrchestrator(MemoryManager(db, embedder))


@router.post("/chat")
async def chat(request: ChatRequest):
    async with async_session() as session:
        db = PostgresDB(session)
        orchestrator = make_orchestrator(db)
        return StreamingResponse(
            orchestrator.process_message(
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                message=request.message,
            ),
            media_type="text/plain",
        )


@router.get("/conversations/{user_id}")
async def list_conversations(user_id: str, limit: int = 50, db: PostgresDB = Depends(get_session)):
    convs = await db.get_conversations(user_id, limit)
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "category": c.category,
            "message_count": c.message_count,
            "created_at": c.created_at.isoformat(),
        }
        for c in convs
    ]


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, db: PostgresDB = Depends(get_session)):
    await db.delete_conversation(conv_id)
    return {"status": "deleted", "conv_id": conv_id}


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, limit: int = 100, db: PostgresDB = Depends(get_session)):
    msgs = await db.get_messages(conv_id, limit)
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(msgs)
    ]


@router.delete("/messages/{msg_id}")
async def delete_message(msg_id: str, db: PostgresDB = Depends(get_session)):
    await db.delete_message(msg_id)
    return {"status": "deleted", "msg_id": msg_id}


@router.get("/conversations/{conv_id}/export")
async def export_conversation(conv_id: str, db: PostgresDB = Depends(get_session)):
    msgs = await db.get_messages(conv_id, 10000)
    lines = []
    for m in reversed(msgs):
        lines.append(f"{m.role.upper()} ({m.created_at.isoformat()}):")
        lines.append(m.content)
        lines.append("")
    return {"text": "\n".join(lines), "count": len(msgs)}


@router.websocket("/ws/chat/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: str):
    await websocket.accept()
    async with async_session() as session:
        db = PostgresDB(session)
        orchestrator = make_orchestrator(db)
        try:
            while True:
                data = await websocket.receive_json()
                async for chunk in orchestrator.process_message(
                    user_id=user_id,
                    conversation_id=data["conversation_id"],
                    message=data["message"],
                ):
                    await websocket.send_json({"type": "chunk", "content": chunk})
                await websocket.send_json({"type": "done"})
        except WebSocketDisconnect:
            pass
