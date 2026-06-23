from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings


class NineRouterProvider:

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.nine_router_api_key,
            base_url=settings.nine_router_base_url,
        )

    async def stream(self, model: str, messages: list[dict], max_tokens: int = 1000, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            text = delta.content or getattr(delta, "reasoning_content", None)
            if text:
                yield text

    async def complete(self, model: str, prompt: str, max_tokens: int = 200, temperature: float = 0.3) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


class LLMGateway:

    def __init__(self):
        self.nine_router = NineRouterProvider()

    async def stream(self, model: str, messages: list[dict], max_tokens: int = 1000, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        async for chunk in self.nine_router.stream(model, messages, max_tokens, temperature):
            yield chunk

    async def complete(self, model: str, prompt: str, max_tokens: int = 200, temperature: float = 0.3) -> str:
        return await self.nine_router.complete(model, prompt, max_tokens, temperature)


llm_gateway = LLMGateway()
