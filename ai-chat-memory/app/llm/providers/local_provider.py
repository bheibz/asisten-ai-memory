from typing import AsyncGenerator

import httpx


class LocalProvider:

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)

    async def stream(self, model: str, messages: list[dict], max_tokens: int = 1000, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            },
        )
        async for line in response.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                import json
                chunk = json.loads(line[6:])
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    yield delta["content"]

    async def complete(self, model: str, prompt: str, max_tokens: int = 200, temperature: float = 0.3) -> str:
        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
