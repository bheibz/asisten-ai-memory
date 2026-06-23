import json
import time
from datetime import datetime
from typing import Optional


class MemoryStore:

    def __init__(self):
        self._data: dict[str, str] = {}
        self._lists: dict[str, list] = {}
        self._ttl: dict[str, float] = {}

    def _flush_expired(self):
        now = time.time()
        expired = [k for k, t in self._ttl.items() if t < now]
        for k in expired:
            self._data.pop(k, None)
            self._lists.pop(k, None)
            self._ttl.pop(k, None)

    def _cleanup(self):
        self._flush_expired()
        if len(self._data) > 10000:
            oldest = sorted(self._ttl.items(), key=lambda x: x[1])[:len(self._ttl)//2]
            for k, _ in oldest:
                self._data.pop(k, None)
                self._lists.pop(k, None)
                self._ttl.pop(k, None)

    async def get(self, key: str) -> Optional[str]:
        self._cleanup()
        return self._data.get(key)

    async def set(self, key: str, value: str, ttl: int = None):
        self._cleanup()
        self._data[key] = value
        if ttl:
            self._ttl[key] = time.time() + ttl

    async def delete(self, key: str):
        self._data.pop(key, None)
        self._lists.pop(key, None)
        self._ttl.pop(key, None)

    async def lrange(self, key: str, start: int, end: int) -> list:
        lst = self._lists.get(key, [])
        return lst[start:end] if end >= 0 else lst[start:]

    async def rpush(self, key: str, value: str):
        self._cleanup()
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].append(value)

    async def ltrim(self, key: str, start: int, end: int):
        lst = self._lists.get(key, [])
        self._lists[key] = lst[start:end] if end >= 0 else lst[start:]

    async def expire(self, key: str, ttl: int):
        self._ttl[key] = time.time() + ttl

    async def incr(self, key: str) -> int:
        self._cleanup()
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val)
        return val


class RedisClient:

    def __init__(self):
        self._fallback = MemoryStore()
        self.client = self._fallback
        self._real_client = None

    async def connect(self):
        try:
            import redis.asyncio as redis
            from app.config import settings
            self._real_client = await redis.from_url(
                settings.redis_url, decode_responses=True, max_connections=20, socket_connect_timeout=2
            )
            await self._real_client.ping()
            self.client = self._real_client
            print("[Redis] Connected to", settings.redis_url)
        except Exception:
            print("[Redis] Not available, using in-memory fallback")
            self.client = self._fallback

    async def disconnect(self):
        if self._real_client:
            await self._real_client.close()

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int = None):
        await self.client.set(key, value, ttl)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def lrange(self, key: str, start: int, end: int) -> list:
        return await self.client.lrange(key, start, end)

    async def rpush(self, key: str, value: str):
        await self.client.rpush(key, value)

    async def ltrim(self, key: str, start: int, end: int):
        await self.client.ltrim(key, start, end)

    async def expire(self, key: str, ttl: int):
        await self.client.expire(key, ttl)

    async def incr(self, key: str) -> int:
        return await self.client.incr(key)

    async def get_response(self, prompt: str, user_id: str) -> Optional[str]:
        from app.utils.hashing import hash_prompt
        key = f"cache:{hash_prompt(prompt, user_id)}"
        return await self.get(key)

    async def store_response(self, prompt: str, user_id: str, response: str, ttl: int = 3600):
        from app.utils.hashing import hash_prompt
        key = f"cache:{hash_prompt(prompt, user_id)}"
        await self.set(key, response, ttl)

    async def get_working_memory(self, user_id: str, conv_id: str, limit: int = 5) -> list[dict]:
        key = f"session:{user_id}:{conv_id}:messages"
        messages = await self.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]

    async def update_working_memory(self, user_id: str, conv_id: str, user_msg: str, ai_response: str, max_messages: int = 10, ttl: int = 1800):
        key = f"session:{user_id}:{conv_id}:messages"
        now = datetime.now().isoformat()
        await self.rpush(key, json.dumps({"role": "user", "content": user_msg, "timestamp": now}))
        await self.rpush(key, json.dumps({"role": "assistant", "content": ai_response, "timestamp": now}))
        await self.ltrim(key, -max_messages, -1)
        await self.expire(key, ttl)


redis_client = RedisClient()
