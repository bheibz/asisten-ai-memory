import time
from fastapi import Request
from fastapi.responses import JSONResponse

from app.utils.logger import setup_logger
from app.utils.errors import AppError, RateLimitError

logger = setup_logger(__name__)

# ── Rate limit config ───────────────────────────────────────────────────

_RATE_LIMIT_WINDOW = 60      # seconds
_RATE_LIMIT_MAX = 30         # requests per window per user
_RATE_LIMIT_HARD = 60        # hard cap (absolute limit)


async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {elapsed:.3f}s"
    )
    return response


async def rate_limiting_middleware(request: Request, call_next):
    """Rate limiting middleware with soft + hard caps."""
    from app.db.redis_client import redis_client

    user_id = request.headers.get("X-User-ID", "anonymous")
    client_ip = request.client.host if request.client else "unknown"
    soft_key = f"ratelimit:{user_id}"
    hard_key = f"ratelimit_hard:{client_ip}"

    # Soft cap: per-user, per-minute
    count = await redis_client.client.incr(soft_key)
    if count == 1:
        await redis_client.client.expire(soft_key, _RATE_LIMIT_WINDOW)
    if count > _RATE_LIMIT_MAX:
        raise RateLimitError(
            f"Rate limit exceeded ({_RATE_LIMIT_MAX} req/min). "
            f"Retry after {_RATE_LIMIT_WINDOW}s."
        )

    # Hard cap: per-IP, absolute ceiling
    hard_count = await redis_client.client.incr(hard_key)
    if hard_count == 1:
        await redis_client.client.expire(hard_key, _RATE_LIMIT_WINDOW)
    if hard_count > _RATE_LIMIT_HARD:
        raise RateLimitError(
            f"Hard rate limit exceeded ({_RATE_LIMIT_HARD} req/min)."
        )

    return await call_next(request)


async def error_handling_middleware(request: Request, call_next):
    """Global error handler middleware — catches AppError and friends."""
    try:
        return await call_next(request)
    except AppError as exc:
        logger.warning(
            f"AppError [{exc.status_code}] {request.method} {request.url.path}: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "status_code": exc.status_code},
        )
    except Exception as exc:
        logger.exception(
            f"Unhandled error {request.method} {request.url.path}: {exc}"
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "status_code": 500},
        )
