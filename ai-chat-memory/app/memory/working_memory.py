import json
from datetime import datetime

from app.config import settings
from app.db.redis_client import redis_client


class WorkingMemory:

    async def get(self, user_id: str, conv_id: str, limit: int = 5) -> list[dict]:
        return await redis_client.get_working_memory(user_id, conv_id, limit)

    async def update(self, user_id: str, conv_id: str, user_msg: str, ai_response: str):
        await redis_client.update_working_memory(
            user_id, conv_id, user_msg, ai_response,
            max_messages=settings.max_working_memory_messages,
            ttl=settings.working_memory_ttl,
        )

    async def clear(self, user_id: str, conv_id: str):
        key = f"session:{user_id}:{conv_id}:messages"
        await redis_client.delete(key)
