"""
DeepSeek native provider — OpenAI-compatible API.
Free tier: 500 requests/day. No rate limits like OpenRouter free.
"""

import logging
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DeepSeekProvider:
    """DeepSeek native API provider (OpenAI-compatible endpoint)."""

    def __init__(self):
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.api_key = settings.deepseek_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def stream(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    raise RuntimeError(
                        f"DeepSeek error {resp.status_code}: {error_text.decode()[:300]}"
                    )
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            import json
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except Exception:
                            continue

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.3,
    ) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"DeepSeek error {resp.status_code}: {resp.text[:300]}"
                )
            data = resp.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            return msg.get("content", "") or ""
