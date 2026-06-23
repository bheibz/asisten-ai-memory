from datetime import datetime

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, MemoryFact, Message, SessionSummary, User
from app.db.database import async_session


async def get_session():
    async with async_session() as session:
        yield PostgresDB(session)


class PostgresDB:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: str):
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, username: str, email: str = None) -> User:
        user = User(username=username, email=email)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_or_create_user(self, username: str, email: str = None) -> User:
        result = await self.session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user:
            user = await self.create_user(username, email)
        return user

    async def get_user_profile(self, user_id: str) -> dict:
        user = await self.get_user(user_id)
        return user.ai_profile if user else {}

    async def update_user_profile(self, user_id: str, profile: dict):
        await self.session.execute(
            update(User).where(User.id == user_id).values(ai_profile=profile, updated_at=datetime.now())
        )
        await self.session.commit()

    async def create_conversation(self, user_id: str, title: str = None, category: str = None) -> Conversation:
        conv = Conversation(user_id=user_id, title=title, category=category)
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def get_conversations(self, user_id: str, limit: int = 20, offset: int = 0):
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.is_archived == False)
            .order_by(Conversation.updated_at.desc())
            .limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def get_conversation(self, conv_id: str):
        result = await self.session.execute(select(Conversation).where(Conversation.id == conv_id))
        return result.scalar_one_or_none()

    async def save_message(self, conv_id: str, role: str, content: str, **kwargs):
        msg = Message(conversation_id=conv_id, role=role, content=content, **kwargs)
        self.session.add(msg)
        await self.session.commit()
        return msg

    async def get_messages(self, conv_id: str, limit: int = 50, offset: int = 0):
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def get_message_count(self, conv_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Message).where(Message.conversation_id == conv_id)
        )
        return result.scalar() or 0

    async def mark_compressed(self, conv_id: str, up_to: int):
        subq = select(Message.id).where(
            Message.conversation_id == conv_id
        ).order_by(Message.created_at.desc()).offset(up_to)
        await self.session.execute(
            update(Message).where(Message.id.in_(subq)).values(compressed=True)
        )
        await self.session.commit()

    async def save_session_summary(self, user_id: str, conv_id: str, summary: str, **kwargs):
        ss = SessionSummary(user_id=user_id, conversation_id=conv_id, summary=summary, **kwargs)
        self.session.add(ss)
        await self.session.commit()

    async def find_fact(self, user_id: str, fact_type: str, fact_key: str):
        result = await self.session.execute(
            select(MemoryFact).where(
                MemoryFact.user_id == user_id,
                MemoryFact.fact_type == fact_type,
                MemoryFact.fact_key == fact_key,
            )
        )
        return result.scalar_one_or_none()

    async def insert_fact(self, user_id: str, conv_id: str, fact: dict):
        mf = MemoryFact(
            user_id=user_id,
            fact_type=fact.get("type", "knowledge"),
            fact_key=fact.get("key"),
            fact_value=fact.get("value", ""),
            source_conversation=conv_id,
        )
        self.session.add(mf)
        await self.session.commit()

    async def update_fact(self, fact_id: str, value: str):
        await self.session.execute(
            update(MemoryFact).where(MemoryFact.id == fact_id).values(
                fact_value=value, access_count=MemoryFact.access_count + 1, updated_at=datetime.now()
            )
        )
        await self.session.commit()

    async def delete_fact(self, fact_id: str):
        await self.session.execute(delete(MemoryFact).where(MemoryFact.id == fact_id))
        await self.session.commit()

    async def get_user_facts(self, user_id: str):
        result = await self.session.execute(
            select(MemoryFact).where(MemoryFact.user_id == user_id).order_by(MemoryFact.decay_score.desc())
        )
        return result.scalars().all()

    async def get_all_facts_for_decay(self):
        result = await self.session.execute(select(MemoryFact).where(MemoryFact.decay_score > 0.1))
        return result.scalars().all()

    async def update_decay_score(self, fact_id: str, new_score: float):
        await self.session.execute(
            update(MemoryFact).where(MemoryFact.id == fact_id).values(
                decay_score=new_score, updated_at=datetime.now()
            )
        )
        await self.session.commit()

    async def archive_fact(self, fact_id: str):
        await self.session.execute(delete(MemoryFact).where(MemoryFact.id == fact_id))
        await self.session.commit()
