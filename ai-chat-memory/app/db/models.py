import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_id():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_id)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    settings = Column(JSON, default=dict)
    ai_profile = Column(JSON, default=lambda: {
        "name": None,
        "language_pref": "id",
        "expertise_level": "general",
        "interests": [],
        "communication_style": "casual",
        "known_facts": {},
    })
    total_tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memory_facts = relationship("MemoryFact", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=gen_id)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=True)
    category = Column(String(50), nullable=True)
    summary = Column(Text, nullable=True)
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    model_used = Column(String(50), nullable=True)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=gen_id)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    model_used = Column(String(50), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    compressed = Column(Boolean, default=False)
    extra = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)

    conversation = relationship("Conversation", back_populates="messages")


class MemoryFact(Base):
    __tablename__ = "memory_facts"

    id = Column(String(36), primary_key=True, default=gen_id)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fact_type = Column(String(50), nullable=False)
    fact_key = Column(String(200), nullable=True)
    fact_value = Column(Text, nullable=False)
    source_conversation = Column(String(36), ForeignKey("conversations.id"), nullable=True)
    confidence = Column(Float, default=1.0)
    access_count = Column(Integer, default=0)
    decay_score = Column(Float, default=1.0)
    last_accessed = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="memory_facts")


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id = Column(String(36), primary_key=True, default=gen_id)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    summary = Column(Text, nullable=False)
    key_topics = Column(JSON, default=list)
    token_count = Column(Integer, nullable=True)
    original_tokens = Column(Integer, nullable=True)
    compression_ratio = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
