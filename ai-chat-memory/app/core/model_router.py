"""
Model router with multi-provider free-model pool, exponential backoff,
and circuit breaker for rate-limited models.
"""

import time
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Free model pools (per tier) ─────────────────────────────────────────
# Priority-ordered: models are tried in order within each tier.
# All models end in :free (OpenRouter free tier).

MODEL_POOLS: dict[str, list[str]] = {
    # All models verified working on OpenRouter free tier.
    # Ordered by reliability: most reliable first.
    "simple": [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "deepseek/deepseek-r1:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "moderate": [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "complex": [
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "creative": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "coding": [
        "qwen/qwen3-coder:free",
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
    ],
    "writing": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "research": [
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "casual": [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "deepseek/deepseek-r1:free",
        "nousresearch/deephermes-3-llama-3-8b:free",
        "moonshotai/kimi-k2-instruct-0905:free",
        "mistralai/mistral-7b-instruct:free",
    ],
}

# ── Backoff config ──────────────────────────────────────────────────────

INITIAL_BACKOFF_SEC = 2.0
MAX_BACKOFF_SEC = 16.0
BACKOFF_MULTIPLIER = 2.0
CIRCUIT_BREAKER_COOLDOWN_SEC = 60   # 1 menit skip model yang kena 429
CIRCUIT_BREAKER_THRESHOLD = 3         # kena 429 3x berturut-turut → break
NOT_FOUND_COOLDOWN_SEC = 3600         # 1 jam skip model 404 (doesn't exist)


class ModelRouter:
    """Smart model selector with multi-provider pool + circuit breaker."""

    # Backward-compatible alias
    MODEL_TIERS = {k: {"primary": v[0], "fallback": v[1] if len(v) > 1 else v[0]}
                   for k, v in MODEL_POOLS.items()}

    def __init__(self, llm_gateway=None):
        self.gateway = llm_gateway
        self._models_cache: list[dict] = []
        self._loaded = False
        self._cache_expires_at = 0.0
        self._cache_ttl = 300

        # Circuit breaker state: {model_id: (failure_count, cooldown_until)}
        self._circuit_breakers: dict[str, tuple[int, float]] = {}

    # ── Public API ──────────────────────────────────────────────────

    async def get_models(self) -> list[dict]:
        now = time.time()
        if self._models_cache is None or now > self._cache_expires_at:
            self._models_cache = []
            self._loaded = False
            if self.gateway:
                try:
                    self._models_cache = await self.gateway.get_models()
                    self._loaded = True
                    self._cache_expires_at = now + self._cache_ttl
                except Exception as e:
                    logger.error(f"Failed to load models from gateway: {e}")
                    self._models_cache = []
                    self._loaded = False
        return self._models_cache

    async def ensure_loaded(self):
        if not self._loaded:
            await self.get_models()

    async def select_model(
        self, complexity: str = "", category: str = "",
        token_budget: int = 10000, force_smart: bool = False,
    ) -> str:
        """Select the best available model for this request."""
        tier_key = force_smart and "complex" or category or complexity or "simple"
        pool = MODEL_POOLS.get(tier_key, MODEL_POOLS["simple"])

        # Check which models are actually available via gateway
        if self._models_cache:
            available_ids = {m.get("id") for m in self._models_cache}

            for model in pool:
                if model not in available_ids:
                    continue
                if self._is_circuit_broken(model):
                    continue
                return model

            # All pool models are either unavailable or circuit-broken
            # Fall back to any available model
            for model in pool:
                if model in available_ids:
                    return model
            if available_ids:
                fallback = next(iter(available_ids))
                logger.warning(f"No pool models available, using: {fallback}")
                return fallback

        # No gateway models loaded — return first pool model
        return pool[0]

    async def on_error(self, model: str, error: Exception) -> Optional[float]:
        """
        Called when a model fails. Returns the recommended delay (seconds)
        before retrying, or None if this model should not be retried.
        """
        is_rate_limited = self._is_rate_limit_error(error)
        is_not_found = self._is_not_found_error(error)

        if is_not_found:
            # Model doesn't exist — block for a long time
            self._circuit_breakers[model] = (999, time.time() + NOT_FOUND_COOLDOWN_SEC)
            logger.warning(f"Model {model} not found, blocking for {NOT_FOUND_COOLDOWN_SEC}s")
            return 0.0  # skip immediately, no delay

        if is_rate_limited:
            count, _ = self._circuit_breakers.get(model, (0, 0))
            count += 1
            if count >= CIRCUIT_BREAKER_THRESHOLD:
                cooldown = time.time() + CIRCUIT_BREAKER_COOLDOWN_SEC
                self._circuit_breakers[model] = (count, cooldown)
                logger.warning(
                    f"Circuit breaker OPEN for {model} "
                    f"({count} rate limits, cooldown {CIRCUIT_BREAKER_COOLDOWN_SEC}s)"
                )
                return INITIAL_BACKOFF_SEC
            else:
                self._circuit_breakers[model] = (count, 0)
                delay = min(INITIAL_BACKOFF_SEC * (BACKOFF_MULTIPLIER ** (count - 1)),
                            MAX_BACKOFF_SEC)
                return delay
        else:
            # Non-rate-limit errors — no backoff, just try next model
            return 0.0

    async def on_success(self, model: str):
        """Reset circuit breaker for a model that succeeded."""
        self._circuit_breakers.pop(model, None)

    # ── Internal ────────────────────────────────────────────────────

    def _is_circuit_broken(self, model: str) -> bool:
        """Check if a model is currently in circuit-breaker cooldown."""
        if model not in self._circuit_breakers:
            return False
        _, cooldown_until = self._circuit_breakers[model]
        if cooldown_until > time.time():
            return True
        # Cooldown expired — clear the breaker
        self._circuit_breakers.pop(model, None)
        return False

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        """Detect if an error is a 429 / rate limit."""
        msg = str(error).lower()
        return any(kw in msg for kw in (
            "429", "rate limit", "rate-limited", "too many requests",
            "try again later", "retry",
        ))

    @staticmethod
    def _is_not_found_error(error: Exception) -> bool:
        """Detect if a model doesn't exist (404)."""
        msg = str(error).lower()
        return "404" in msg or "unavailable" in msg or "not found" in msg
