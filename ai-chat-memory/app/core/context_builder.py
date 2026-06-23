"""
Context builder — constructs the full system context including
date/time, Hijri calendar, knowledge base, tone, and system prompt.
"""

from datetime import datetime
from typing import Optional

from app.db.database import async_session
from app.db.postgres import PostgresDB

# ── Static day/month names ──────────────────────────────────────────────

_DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]
_HIJRI_MONTHS = [
    "Muharram", "Safar", "Rabi'ul Awwal", "Rabi'ul Akhir",
    "Jumadil Awwal", "Jumadil Akhir", "Rajab", "Sya'ban",
    "Ramadhan", "Syawwal", "Dzulqa'dah", "Dzulhijjah",
]

# ── Tone detection ──────────────────────────────────────────────────────

_TONE_MAP = {
    "sympathetic": frozenset({"sedih", "kecewa", "sakit", "lelah", "sendiri",
                               "betah", "pusing", "rindu", "kehilangan", "menangis"}),
    "calm": frozenset({"marah", "kesal", "sebal", "geram", "jengkel",
                        "muak", "jijik", "benci"}),
    "cheerful": frozenset({"senang", "bahagia", "syukur", "ceria",
                            "seneng", "bangga", "terharu"}),
    "anxious": frozenset({"cemas", "khawatir", "takut", "gelisah",
                           "deg", "debar", "panic"}),
    "tired": frozenset({"capek", "lelah", "mengantuk", "letih", "lesu"}),
}

_TONE_INSTRUCTIONS = {
    "sympathetic": "\n\nTONE: User seems sad or struggling. Respond with extra warmth and empathy.",
    "calm": "\n\nTONE: User seems upset. Stay calm, don't be defensive, be understanding.",
    "cheerful": "\n\nTONE: User is cheerful! Match their positive energy and enthusiasm.",
    "anxious": "\n\nTONE: User seems anxious or worried. Reassure them, be calm and supportive.",
    "tired": "\n\nTONE: User seems tired or low energy. Be gentle, don't push too much.",
}


class ContextBuilder:

    @staticmethod
    def detect_tone(message: str) -> str:
        msg = message.lower()
        for tone, words in _TONE_MAP.items():
            if any(w in msg for w in words):
                return tone
        return "neutral"

    @staticmethod
    def build_time_context() -> str:
        now = datetime.now()
        date_str = f"hari {_DAYS_ID[now.weekday()]}, {now.day} {_MONTHS_ID[now.month - 1]} {now.year}"
        ctx = f"\n[CURRENT DATE] Sekarang {date_str}, jam {now.hour:02d}:{now.minute:02d} WIB."

        # Hijri date
        try:
            from hijri_converter import Gregorian as G
            h = G(now.year, now.month, now.day).to_hijri()
            ctx += f"\n[HIJRI DATE] {h.day} {_HIJRI_MONTHS[h.month - 1]} {h.year} H."
        except Exception:
            pass

        return ctx

    @staticmethod
    async def build_knowledge_context(user_id: str, query_needs_search: bool,
                                       current_message: str) -> str:
        """Build knowledge base and pinned notes context."""
        parts = []

        try:
            async with async_session() as session:
                db = PostgresDB(session)

                # Pinned notes
                pinned = await db.get_pinned_knowledge(user_id)
                if pinned:
                    lines = ["[PINNED NOTES]"]
                    for kb in pinned:
                        tag_str = f" #{' #'.join(kb.tags)}" if kb.tags else ""
                        lines.append(f"📌 {kb.title}{tag_str}")
                        if kb.content:
                            lines.append(f"   {kb.content[:200]}")
                    parts.append("\n".join(lines))

                # Searched knowledge
                if query_needs_search:
                    searched = await db.search_knowledge(user_id, current_message, 3)
                    if searched:
                        lines = ["[KNOWLEDGE BASE]"]
                        for kb in searched:
                            lines.append(f"• {kb.title}: {kb.content[:200]}")
                        parts.append("\n".join(lines))
        except Exception:
            pass

        return "\n" + "\n".join(parts) if parts else ""

    @staticmethod
    def get_system_prompt(category: str, tone: str = "neutral") -> str:
        """Return base system prompt with tone instruction."""
        from app.core.prompt_compiler import PromptCompiler

        base = PromptCompiler.SYSTEM_PROMPTS.get(
            category, PromptCompiler.SYSTEM_PROMPTS["default"]
        )
        tone_instr = _TONE_INSTRUCTIONS.get(tone, "")
        return base + tone_instr
