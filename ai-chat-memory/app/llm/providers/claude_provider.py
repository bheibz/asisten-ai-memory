from typing import AsyncGenerator

from anthropic import AsyncAnthropic

from app.config import settings


class ClaudeProvider:

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def stream(self, model: str, messages: list[dict], max_tokens: int = 1000, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        system = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        async with self.client.messages.stream(
            model=model,
            system=system,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def complete(self, model: str, prompt: str, max_tokens: int = 200, temperature: float = 0.3) -> str:
        response = await self.client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.content[0].text if response.content else ""
