import hashlib
import json

import httpx

from app.config import settings


class Embedder:

    def __init__(self):
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.api_key = settings.openrouter_api_key or settings.openai_api_key or "sk-placeholder"
        self.model = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        if not settings.openai_api_key and not settings.openrouter_api_key:
            return self._fake_embed(text)
        try:
            return await self._embed([text])
        except Exception:
            return self._fake_embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not settings.openai_api_key and not settings.openrouter_api_key:
            return [self._fake_embed(t) for t in texts]
        try:
            return await self._embed(texts)
        except Exception:
            return [self._fake_embed(t) for t in texts]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                content=json.dumps(payload),
            )
            resp.raise_for_status()
            data = resp.json()
            return [d["embedding"] for d in data.get("data", [])]

    def _fake_embed(self, text: str) -> list[float]:
        h = hashlib.md5(text.encode()).digest()
        vec = [((h[i] if i < len(h) else 0) / 255.0) * 2 - 1 for i in range(128)]
        vec = vec + [0.0] * (1536 - len(vec))
        return vec
