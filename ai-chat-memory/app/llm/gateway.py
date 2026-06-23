import json
import logging
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OpenRouterProvider:

    def __init__(self):
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.api_key = settings.openrouter_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ai-chat-memory",
            "X-Title": settings.app_name,
        }

    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}{path}",
                headers=self.headers,
                content=json.dumps(payload),
            )
            if resp.status_code >= 400:
                logger.error(f"OpenRouter POST {path} failed: {resp.status_code} {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
            )
            if resp.status_code >= 400:
                logger.error(f"OpenRouter GET {path} failed: {resp.status_code} {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()

    async def stream(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        reasoning: bool = True,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if reasoning:
            payload["reasoning"] = {"enabled": True}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    content=json.dumps(payload),
                ) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        raise RuntimeError(f"OpenRouter error {resp.status_code}: {error_text.decode()[:200]}")
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            try:
                                data = json.loads(line[6:])
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                                elif "reasoning_content" in delta and delta["reasoning_content"]:
                                    yield delta["reasoning_content"]
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue
        except RuntimeError:
            raise
        except Exception as e:
            # Yield error as text to ensure stream closes cleanly
            yield f"\n⚠️ Streaming error: {e}\n"
            return

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.3,
        reasoning: bool = False,
    ) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if reasoning:
            payload["reasoning"] = {"enabled": True}

        data = await self._post("/chat/completions", payload)
        msg = data.get("choices", [{}])[0].get("message", {})
        return msg.get("content", "") or ""

    async def get_models(self) -> list[dict]:
        try:
            data = await self._get("/models")
            models = data.get("data", [])
            logger.info(f"Loaded {len(models)} models from OpenRouter")
            return models
        except Exception as e:
            logger.error(f"Failed to load models from OpenRouter: {e}")
            return []


from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.deepseek_provider import DeepSeekProvider
from app.llm.providers.cerebras_provider import CerebrasProvider

class LLMGateway:

    # Models routed to native providers (not OpenRouter)
    DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner", "deepseek-r1"}
    CEREBRAS_MODELS = {"llama3.1-8b", "llama-3.3-70b", "llama3.3-70b"}

    def __init__(self):
        self.provider = OpenRouterProvider()
        self.deepseek = DeepSeekProvider()
        self.cerebras = CerebrasProvider()

    def _use_deepseek(self, model: str) -> bool:
        return (
            bool(settings.deepseek_api_key)
            and any(m in model for m in self.DEEPSEEK_MODELS)
            and ":free" not in model
        )

    def _use_cerebras(self, model: str) -> bool:
        return (
            bool(settings.cerebras_api_key)
            and any(m in model for m in self.CEREBRAS_MODELS)
        )

    async def stream(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        reasoning: bool = True,
    ) -> AsyncGenerator[str, None]:
        if self._use_deepseek(model):
            async for chunk in self.deepseek.stream(model, messages, max_tokens, temperature):
                yield chunk
        elif self._use_cerebras(model):
            async for chunk in self.cerebras.stream(model, messages, max_tokens, temperature):
                yield chunk
        else:
            async for chunk in self.provider.stream(model, messages, max_tokens, temperature, reasoning=reasoning):
                yield chunk

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.3,
        reasoning: bool = False,
    ) -> str:
        if self._use_deepseek(model):
            return await self.deepseek.complete(model, prompt, max_tokens, temperature)
        if self._use_cerebras(model):
            return await self.cerebras.complete(model, prompt, max_tokens, temperature)
        return await self.provider.complete(model, prompt, max_tokens, temperature, reasoning=reasoning)

    async def get_models(self) -> list[dict]:
        return await self.provider.get_models()


llm_gateway = LLMGateway()
