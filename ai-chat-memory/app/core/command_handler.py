"""
Consolidated command handler — all memory, knowledge, reminder, and name commands.
Replaces the duplicated _handle_memory_command / _execute_cmd in the orchestrator.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.db.postgres import PostgresDB
from app.memory.memory_manager import MemoryManager
from app.llm.embeddings import Embedder
from app.db.vector_store import vector_store
from app.llm.gateway import llm_gateway
from app.db.database import async_session

# ── Command patterns (compiled once) ──────────────────────────────────────

_MEMORY_PATTERNS = {
    "ganti_namamu": re.compile(
        r"(?:aku\s+)?(?:ganti|ubah|set|panggil)\s+(?:(?:nama\s+)?kamu|namamu)\s+(?:menjadi|jadi|:)?\s*([a-zA-Z0-9_]+)",
        re.IGNORECASE,
    ),
    "ganti_namaku": re.compile(
        r"(?:aku\s+)?(?:ganti|ubah|set|panggil)\s+(?:(?:nama\s+)?(?:aku|saya)|namaku)\s+(?:menjadi|jadi|:)?\s*([a-zA-Z0-9_]+)",
        re.IGNORECASE,
    ),
    "ingat": re.compile(
        r"(?:ingat|catat|remember|save|note)\s+(?:bahwa|:|\s)?\s*(.+)",
        re.IGNORECASE,
    ),
    "lupa": re.compile(
        r"(?:lupa|forget|hapus|delete|remove)\s+(?:bahwa|:|\s)?\s*(.+)",
        re.IGNORECASE,
    ),
    "update": re.compile(
        r"(?:perbaharui|ubah|update|ganti|edit|change)\s+(?:catatan|memory|memori|note)?\s*(?:tentang|mengenai|:)?\s*(.+)",
        re.IGNORECASE,
    ),
}

_KNOWLEDGE_PATTERNS = {
    "simpan": re.compile(
        r"(?:simpan|catat|save|note)\s+(?:catatan|knowledge|pengetahuan)?\s*[:\-]?\s*([\s\S]+)",
        re.IGNORECASE,
    ),
    "cari_catatan": re.compile(
        r"(?:cari|search)\s+(?:di\s+)?(?:catatan|knowledge|notes|pengetahuan)\s+(.+)",
        re.IGNORECASE,
    ),
}

_REMINDER_PATTERN = re.compile(
    r"(?:ingatkan|remind|reminder)\s+(?:aku|saya|gue|gw)?\s*(?:tentang|untuk|buat)?\s*[:]?\s*(.+)",
    re.IGNORECASE,
)

_SKIP_WORDS = {"aku", "saya", "my", "i", "gue", "gw"}


def _extract_memory_key(content: str) -> str:
    """Extract the first meaningful word as the memory key."""
    words = content.split()
    if len(words) >= 2 and words[0].lower() in _SKIP_WORDS:
        return words[1] if len(words) > 1 else words[0]
    return words[0] if words else "catatan"


class CommandHandler:
    """Handles all user-initiated commands: memory, knowledge, reminders, names."""

    def __init__(self, db: PostgresDB):
        self.db = db
        self.embedder = Embedder()
        self.memory = MemoryManager(db, self.embedder)

    async def handle(self, user_id: str, message: str) -> Optional[str]:
        """
        Detect and execute a command from the user message.
        Returns the response string if a command was handled, None otherwise.
        """
        msg_lower = message.lower().strip()

        # 1. Memory commands
        result = await self._try_memory_command(user_id, msg_lower)
        if result is not None:
            return result

        # 2. Knowledge commands
        result = await self._try_knowledge_command(user_id, msg_lower)
        if result is not None:
            return result

        # 3. Reminder commands
        result = await self._try_reminder_command(user_id, msg_lower)
        if result is not None:
            return result

        return None

    # ── Memory commands ───────────────────────────────────────────────

    async def _try_memory_command(self, user_id: str, msg_lower: str) -> Optional[str]:
        for cmd, pattern in _MEMORY_PATTERNS.items():
            m = pattern.match(msg_lower)
            if not m:
                continue
            content = m.group(1).strip()
            if not content:
                continue

            await self._ensure_user(user_id)

            if cmd == "ganti_namamu":
                await self.db.set_preferred_ai_name(user_id, content)
                return f"✅ Oke, panggil aku *{content}* mulai sekarang!"

            if cmd == "ganti_namaku":
                profile = await self.db.get_user_profile(user_id)
                profile["name"] = content
                await self.db.update_user_profile(user_id, profile)
                return f"✅ Senang kenal, *{content}*!"

            if cmd == "ingat":
                return await self._handle_remember(user_id, content)

            if cmd == "lupa":
                return await self._handle_forget(user_id, content)

            if cmd == "update":
                return await self._handle_update(user_id, content)

        return None

    async def _handle_remember(self, user_id: str, content: str) -> str:
        key = _extract_memory_key(content)
        existing = await self.db.find_fact(user_id, "personal", key)
        if existing:
            # Update existing fact
            await self.db.update_fact(existing.id, content)
            await vector_store.delete(existing.id)
            embed = await self.embedder.embed(f"{key}: {content}")
            await vector_store.upsert(
                "user_memories", existing.id, embed,
                {"id": existing.id, "user_id": user_id, "fact_type": "personal",
                 "content": f"{key}: {content}", "decay_score": 1.0, "access_count": 0},
            )
            return f"✅ Diperbaharui! *{content}*"
        else:
            await self.memory.long_term.store_fact(
                user_id, None, {"type": "personal", "key": key, "value": content}
            )
            return f"✅ Disimpan! *{content}*"

    async def _handle_forget(self, user_id: str, content: str) -> str:
        facts = await self.db.get_user_facts(user_id)
        for f in facts:
            if content.lower() in f.fact_value.lower() or content.lower() in f.fact_key.lower():
                await self.db.delete_fact(f.id)
                await vector_store.delete(f.id)
                return f"🗑️ Dihapus! *{f.fact_key}: {f.fact_value}*"
        return f"🔍 Tidak nemu *{content}*"

    async def _handle_update(self, user_id: str, content: str) -> str:
        facts = await self.db.get_user_facts(user_id)
        if not facts:
            return "📭 Belum ada memory tersimpan."
        for f in facts:
            if content.lower() in f.fact_key.lower() or content.lower() in f.fact_value.lower():
                val = content.split("menjadi")[-1].strip() if "menjadi" in content else content
                await self.db.update_fact(f.id, val)
                await vector_store.delete(f.id)
                embed = await self.embedder.embed(f"{f.fact_key}: {val}")
                await vector_store.upsert(
                    "user_memories", f.id, embed,
                    {"id": f.id, "user_id": user_id, "fact_type": f.fact_type,
                     "content": f"{f.fact_key}: {val}", "decay_score": 1.0, "access_count": 0},
                )
                return f"✅ Diperbaharui: *{f.fact_key}: {val}*"
        return f"🔍 Tidak nemu *{content}*"

    # ── Knowledge commands ────────────────────────────────────────────

    async def _try_knowledge_command(self, user_id: str, msg_lower: str) -> Optional[str]:
        for cmd, pattern in _KNOWLEDGE_PATTERNS.items():
            m = pattern.match(msg_lower)
            if not m:
                continue
            content = m.group(1).strip()
            if not content:
                continue

            await self._ensure_user(user_id)

            if cmd == "simpan":
                return await self._handle_save_knowledge(user_id, content)
            if cmd == "cari_catatan":
                return await self._handle_search_knowledge(user_id, content)
        return None

    async def _handle_save_knowledge(self, user_id: str, content: str) -> str:
        parts = content.split("\n", 1)
        title = parts[0].strip()[:200]
        body = parts[1].strip() if len(parts) > 1 else ""
        if not body:
            body = title
            title = title[:60]

        # Auto-tagging via lightweight model
        tags = []
        try:
            tag_prompt = (
                f"Extract 1-3 tags from this text. Return ONLY comma-separated lowercase words. "
                f"Text: {title[:100]}"
            )
            tag_result = await llm_gateway.complete(
                model="google/gemini-2.0-flash-exp:free",
                prompt=tag_prompt,
                max_tokens=30,
            )
            tags = [t.strip().lower() for t in tag_result.split(",")
                    if t.strip() and len(t.strip()) < 20]
        except Exception:
            pass

        kb = await self.db.create_knowledge(user_id, title, body, tags=tags[:3], source="chat")
        tag_str = f" #{' #'.join(kb.tags)}" if kb.tags else ""
        return f"✅ Catatan disimpan: *{kb.title}*{tag_str}"

    async def _handle_search_knowledge(self, user_id: str, content: str) -> str:
        results = await self.db.search_knowledge(user_id, content, 3)
        if not results:
            return f"🔍 Tidak nemu catatan tentang *{content}*"
        lines = ["📚 Catatan ditemukan:"]
        for kb in results:
            tag_str = f" #{' #'.join(kb.tags)}" if kb.tags else ""
            flag = " 📌" if kb.is_pinned else ""
            lines.append(f"• *{kb.title}*{flag}{tag_str}")
            if kb.content:
                lines.append(f"  {kb.content[:150]}")
        return "\n".join(lines)

    # ── Reminder commands ──────────────────────────────────────────────

    async def _try_reminder_command(self, user_id: str, msg_lower: str) -> Optional[str]:
        m = _REMINDER_PATTERN.match(msg_lower)
        if not m:
            return None
        raw = m.group(1).strip()
        if not raw:
            return None

        await self._ensure_user(user_id)

        import dateparser
        from datetime import datetime

        when = dateparser.parse(raw, languages=["id", "en"])
        if not when:
            when = dateparser.parse("besok", languages=["id"])
        await self.db.create_reminder(user_id, raw, when)
        when_str = when.strftime("%d %b %Y %H:%M") if when else "besok"
        return f"✅ Reminder disimpan: *{raw}* ({when_str})"

    # ── Helpers ────────────────────────────────────────────────────────

    async def _ensure_user(self, user_id: str):
        """Auto-create user if not exists."""
        user = await self.db.get_user(user_id)
        if not user:
            from app.db.models import User as UserModel
            from sqlalchemy import insert
            async with async_session() as session:
                await session.execute(
                    insert(UserModel).values(id=user_id, username=user_id)
                )
                await session.commit()
