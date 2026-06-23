from app.llm.gateway import llm_gateway


class Compressor:

    async def summarize(self, messages: list, max_tokens: int = 200, model: str = "gpt-3.5-turbo") -> str:
        text = "\n".join(
            f"{m.role if hasattr(m, 'role') else m.get('role', 'user')}: "
            f"{m.content if hasattr(m, 'content') else m.get('content', '')}"
            for m in messages
        )
        prompt = (
            f"Compress the following conversation into a concise summary "
            f"(max {max_tokens} tokens). Keep all important information, facts, "
            f"and decisions. Use the same language as the conversation.\n\n{text}"
        )
        summary = await llm_gateway.complete(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
        )
        return summary.strip()
