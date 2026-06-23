import time
from fastapi import Request

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {elapsed:.3f}s")
    return response


async def rate_limiting_middleware(request: Request, call_next):
    from app.db.redis_client import redis_client
    user_id = request.headers.get("X-User-ID", "anonymous")
    key = f"ratelimit:{user_id}"
    count = await redis_client.client.incr(key)
    if count == 1:
        await redis_client.client.expire(key, 60)
    if count > 30:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Max 30 requests/min."})
    return await call_next(request)
