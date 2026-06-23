import logging
from typing import AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)


class ModelRouter:

    MODEL_TIERS = {
        "simple": {
            "primary": "qwen/qwen3-next-80b-a3b-instruct:free",
            "fallback": "meta-llama/llama-3.3-70b-instruct:free",
        },
        "moderate": {
            "primary": "qwen/qwen3-next-80b-a3b-instruct:free",
            "fallback": "meta-llama/llama-3.3-70b-instruct:free",
        },
        "complex": {
            "primary": "qwen/qwen3-next-80b-a3b-instruct:free",
            "fallback": "meta-llama/llama-3.3-70b-instruct:free",
        },
        "creative": {
            "primary": "meta-llama/llama-3.3-70b-instruct:free",
            "fallback": "qwen/qwen3-next-80b-a3b-instruct:free",
        },
        "coding": {
            "primary": "qwen/qwen3-coder:free",
            "fallback": "cohere/north-mini-code:free",
        },
        "writing": {
            "primary": "meta-llama/llama-3.3-70b-instruct:free",
            "fallback": "qwen/qwen3-next-80b-a3b-instruct:free",
        },
        "research": {
            "primary": "qwen/qwen3-next-80b-a3b-instruct:free",
            "fallback": "meta-llama/llama-3.3-70b-instruct:free",
        },
        "casual": {
            "primary": "qwen/qwen3-next-80b-a3b-instruct:free",
            "fallback": "meta-llama/llama-3.3-70b-instruct:free",
        },
    }

    def __init__(self, llm_gateway=None):
        self.gateway = llm_gateway
        self._models_cache = None
        self._loaded = False
        self._cache_expires_at = 0.0
        self._cache_ttl = 300  # 5 minutes

    async def get_models(self) -> list[dict]:
        import time
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

    async def select_model(self, complexity: str = "", category: str = "", token_budget: int = 10000, force_smart: bool = False) -> str:
        await self.ensure_loaded()
        tier = self.MODEL_TIERS.get(force_smart and "complex" or category or complexity or "simple", self.MODEL_TIERS["simple"])
        primary = tier["primary"]
        fallback = tier.get("fallback", primary)
        if self._models_cache:
            available_ids = [m.get("id") for m in self._models_cache]
            if primary in available_ids:
                return primary
            if fallback and fallback in available_ids:
                return fallback
            if available_ids:
                logger.warning(f"Primary {primary} and fallback {fallback} not found, using first available: {available_ids[0]}")
                return available_ids[0]
        logger.warning(f"No models available from gateway, falling back to configured primary: {primary}")
        return primary
