from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db.database import async_session
from app.db.postgres import PostgresDB, get_session
from app.llm.embeddings import Embedder
from app.memory.memory_manager import MemoryManager
from app.core.orchestrator import BrainOrchestrator
from app.core.model_router import ModelRouter
from app.llm.gateway import llm_gateway

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    conversation_id: str
    message: str
    model: str = "openrouter/free"


def make_orchestrator(db: PostgresDB):
    embedder = Embedder()
    return BrainOrchestrator(MemoryManager(db, embedder))


def _categorize_model(model: dict) -> str:
    model_id = model.get("id", "").lower()
    modality = model.get("architecture", {}).get("modality", "").lower()
    supported = [p.lower() for p in model.get("supported_parameters", [])]
    
    # Image/Vision models
    if "image" in modality or "vision" in model_id or "gemini" in model_id and "flash" in model_id:
        return "🖼️ Image"
    
    # Coding models
    if any(kw in model_id for kw in ["coder", "code", "qwen3-coder", "deepseek", "programming"]):
        return "💻 Coding"
    
    # Reasoning models
    if "reasoning" in supported or "include_reasoning" in supported or "reasoning" in model_id:
        return "🧠 Reasoning"
    
    # Multimodal
    if "video" in modality or "audio" in modality:
        return "🎬 Multimodal"
    
    # Default: Chat
    return "💬 Chat"


@router.get("/models")
async def list_models():
    router = ModelRouter(llm_gateway=llm_gateway)
    models = await router.get_models()
    
    categorized = {}
    free_models = []
    
    for m in models:
        model_id = m.get("id", "")
        is_free = model_id.endswith(":free")
        if is_free:
            free_models.append(model_id)
        
        category = _categorize_model(m)
        if category not in categorized:
            categorized[category] = []
        categorized[category].append({
            "id": model_id,
            "name": m.get("name", model_id),
            "free": is_free,
        })
    
    return {
        "models": models,
        "categorized": categorized,
        "free_models": free_models,
        "default": "openrouter/free",
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    async with async_session() as session:
        db = PostgresDB(session)
        orchestrator = make_orchestrator(db)
        if request.model and request.model != "openrouter/free":
            orchestrator.model_override = request.model
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
