from app.config import settings
from app.core.token_counter import count_tokens


class PromptCompiler:

    SYSTEM_PROMPTS = {
        "coding": "You are a senior developer. Be concise. Use code blocks. Skip explanations unless asked. Reply in user's language.",
        "writing": "You are a skilled writer. Match user's tone and style. Be creative but concise. Reply in user's language.",
        "research": "You are a research analyst with web search access. Use [WEB SEARCH RESULTS] below if available. Cite sources. Be thorough but structured. Use bullet points.",
        "casual": "You are a friendly AI assistant. Be natural and brief. Reply in user's language. Remember context from memory.",
        "default": """CAPABILITIES:
- Answering questions, translating languages, summarizing text
- Writing code, debugging, explaining programming concepts
- Explaining complex topics simply, helping with learning
- Writing emails, letters, CVs, brainstorming ideas
- Math & logic, data analysis, problem solving
- Creative writing: poetry, stories, social media content
- Casual chat, discussion, brainstorming

IMPORTANT:
- You HAVE web search capability! When the user asks you to search/check something, look for [WEB SEARCH RESULTS] in the context below. If you see results, use them. If results say "tidak menemukan hasil", tell the user honestly.
- You CAN see current date/time if [CURRENT DATE] is provided below.

CONSTRAINTS:
- You cannot send emails/WhatsApp or open links/files
- Reply in user's language
- Be concise and accurate""",
    }

    def compile(
        self,
        system_context: str,
        user_profile: dict,
        relevant_memories: list,
        recent_messages: list,
        current_message: str,
        max_context_tokens: int = 2000,
        web_results: list = None,
        ai_name: str = None,
    ) -> list[dict]:
        messages = []
        ai_display_name = ai_name or settings.ai_name
        system_content = f"Your name is {ai_display_name}. Always respond directly without showing your internal reasoning or thinking process. Start your response immediately with the answer.\n" + system_context

        if user_profile:
            user_display_name = user_profile.get("name") or ""
            if user_display_name:
                system_content += f"\n\nThe user's name is {user_display_name}. Always address the user as {user_display_name}."
            profile_line = self._compile_profile(user_profile)
            system_content += f"\n\n[USER PROFILE] {profile_line}"

        if relevant_memories:
            mem_text = "\n".join(f"- {m['content']}" for m in relevant_memories[:3])
            system_content += f"\n\n[RELEVANT MEMORY]\n{mem_text}"

        if web_results is not None:
            from app.tools.web_search import web_search as ws
            web_text = ws.format_for_prompt(web_results, current_message)
            system_content += f"\n\n{web_text}"

        messages.append({"role": "system", "content": system_content})

        token_used = count_tokens(system_content)
        remaining = max_context_tokens - token_used - count_tokens(current_message)

        for msg in recent_messages:
            content = msg.get("content", "")
            msg_tokens = count_tokens(content)
            if remaining - msg_tokens < 0:
                break
            messages.append({"role": msg.get("role", "user"), "content": content})
            remaining -= msg_tokens

        user_name = (user_profile or {}).get("name", "")
        prefix = f"[Nama user: {user_name}] " if user_name else ""
        messages.append({"role": "user", "content": prefix + current_message})
        return messages

    def _compile_profile(self, profile: dict) -> str:
        parts = []
        if profile.get("name"):
            parts.append(f"Name:{profile['name']}")
        if profile.get("language_pref"):
            parts.append(f"Lang:{profile['language_pref']}")
        if profile.get("expertise_level"):
            parts.append(f"Level:{profile['expertise_level']}")
        if profile.get("interests"):
            parts.append(f"Interest:{','.join(profile['interests'][:3])}")
        return " | ".join(parts)
