from app.db.postgres import PostgresDB


class ShortTermMemory:

    def __init__(self, db: PostgresDB):
        self.db = db

    async def compress_if_needed(self, user_id: str, conv_id: str, compressor):
        msg_count = await self.db.get_message_count(conv_id)
        if msg_count > 20:
            old_messages = await self.db.get_messages(conv_id, limit=msg_count - 5, offset=0)
            summary = await compressor.summarize(old_messages, max_tokens=200)
            await self.db.save_session_summary(
                user_id, conv_id, summary,
                token_count=len(summary.split()),
                original_tokens=sum(len(m.content.split()) for m in old_messages),
                compression_ratio=len(summary.split()) / max(sum(len(m.content.split()) for m in old_messages), 1),
            )
            await self.db.mark_compressed(conv_id, msg_count - 5)

    async def get_summaries(self, user_id: str, conv_id: str):
        from app.db.models import SessionSummary
        from sqlalchemy import select
        result = await self.db.session.execute(
            select(SessionSummary).where(SessionSummary.conversation_id == conv_id)
            .order_by(SessionSummary.created_at.desc()).limit(3)
        )
        return result.scalars().all()
