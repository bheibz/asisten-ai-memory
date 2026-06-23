"""
Typed application exceptions for consistent error handling.
"""

from typing import Optional


class AppError(Exception):
    """Base application error."""
    status_code: int = 500
    message: str = "Internal server error"

    def __init__(self, detail: Optional[str] = None):
        self.detail = detail or self.message
        super().__init__(self.detail)


# ── API Errors ─────────────────────────────────────────────────────────

class NotFoundError(AppError):
    status_code = 404
    message = "Resource not found"


class ValidationError(AppError):
    status_code = 422
    message = "Validation error"


class RateLimitError(AppError):
    status_code = 429
    message = "Rate limit exceeded"


class UnauthorizedError(AppError):
    status_code = 401
    message = "Unauthorized"


# ── Service Errors ─────────────────────────────────────────────────────

class LLMError(AppError):
    status_code = 502
    message = "LLM service error"


class LLMTimeoutError(LLMError):
    status_code = 504
    message = "LLM service timeout"


class LLMFallbackError(LLMError):
    """All LLM attempts failed."""
    status_code = 502
    message = "All LLM providers failed"


class DatabaseError(AppError):
    status_code = 503
    message = "Database error"


class EmbeddingError(AppError):
    status_code = 503
    message = "Embedding service error"


class SearchError(AppError):
    status_code = 503
    message = "Search service error"
