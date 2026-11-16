"""Conversation storage.

sessions: one row per conversation, owned by an anonymous client id (the browser).
chats:    one row per message, in OpenAI chat format (user / assistant / tool), so a conversation can be
          replayed into the model after a restart. The final assistant message of each turn carries `meta`
          (product cards + tool steps) so the UI can re-render history without re-running anything.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# none_as_null: Python None must be SQL NULL, not a JSON 'null' value
JsonType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class Base(DeclarativeBase):
    pass


class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    chats: Mapped[list["Chat"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True, order_by="Chat.id"
    )


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant', 'tool')", name="chats_role_check"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[list | None] = mapped_column(JsonType)  # assistant -> tools requested
    tool_call_id: Mapped[str | None] = mapped_column(String(64))  # tool -> which call it answers
    meta: Mapped[dict | None] = mapped_column(JsonType)  # final assistant message: {"products": [...], "steps": [...]}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="chats")
