import hashlib
from openai import AsyncOpenAI

from app.config import settings


class Embedder:

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.nine_router_api_key or settings.openai_api_key or "sk-placeholder",
            base_url=settings.nine_router_base_url if settings.nine_router_api_key else None,
        )
        self.model = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        if not settings.openai_api_key and not settings.nine_router_api_key:
            return self._fake_embed(text)
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception:
            return self._fake_embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not settings.openai_api_key and not settings.nine_router_api_key:
            return [self._fake_embed(t) for t in texts]
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [d.embedding for d in response.data]
        except Exception:
            return [self._fake_embed(t) for t in texts]

    def _fake_embed(self, text: str) -> list[float]:
        h = hashlib.md5(text.encode()).digest()
        vec = [((h[i] if i < len(h) else 0) / 255.0) * 2 - 1 for i in range(128)]
        vec = vec + [0.0] * (1536 - len(vec))
        return vec
