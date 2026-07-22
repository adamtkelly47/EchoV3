"""Conversation is a domain-owned aggregate (sessions and their messages),
so — matching the Approvals pattern from Phase 6 — the ORM tables live
here rather than under infrastructure/database/tables/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Boolean, DateTime, ForeignKey, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.conversation.schemas import Channel, ConversationSession, Message, MessageRole
from infrastructure.database.base import Base


class ConversationSessionRow(Base):
    __tablename__ = "conversation_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, index=True)


class MessageRow(Base):
    __tablename__ = "conversation_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversation_sessions.session_id"), index=True
    )
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    channel: Mapped[str] = mapped_column(String, default=Channel.TEXT.value)
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)


class ConversationRepository(Protocol):
    async def save_session(self, session: ConversationSession) -> None: ...
    async def get_session(self, session_id: str) -> ConversationSession | None: ...
    async def list_recent_sessions_for_user(
        self, user_id: str, *, limit: int = 5
    ) -> list[ConversationSession]: ...
    async def save_message(self, message: Message) -> None: ...
    async def get_messages(self, session_id: str) -> list[Message]: ...


class PostgresConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_session(self, session: ConversationSession) -> None:
        row = ConversationSessionRow(
            session_id=session.session_id,
            user_id=session.user_id,
            started_at=session.started_at,
            status=session.status,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_session(self, session_id: str) -> ConversationSession | None:
        row = await self._session.get(ConversationSessionRow, session_id)
        if row is None:
            return None
        return ConversationSession(
            session_id=row.session_id,
            user_id=row.user_id,
            started_at=row.started_at,
            status=row.status,
        )

    async def list_recent_sessions_for_user(
        self, user_id: str, *, limit: int = 5
    ) -> list[ConversationSession]:
        """PROMPT.md Phase 22 implement item 5: "conversation" (dashboard
        card). Most-recent-first, capped — a dashboard summary, not a full
        history browser."""
        result = await self._session.execute(
            select(ConversationSessionRow)
            .where(ConversationSessionRow.user_id == user_id)
            .order_by(ConversationSessionRow.started_at.desc())
            .limit(limit)
        )
        return [
            ConversationSession(
                session_id=row.session_id,
                user_id=row.user_id,
                started_at=row.started_at,
                status=row.status,
            )
            for row in result.scalars().all()
        ]

    async def save_message(self, message: Message) -> None:
        row = MessageRow(
            message_id=message.message_id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            evidence=message.evidence,
            channel=message.channel.value,
            interrupted=message.interrupted,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_messages(self, session_id: str) -> list[Message]:
        result = await self._session.execute(
            select(MessageRow)
            .where(MessageRow.session_id == session_id)
            .order_by(MessageRow.created_at.asc())
        )
        return [
            Message(
                message_id=row.message_id,
                session_id=row.session_id,
                role=MessageRole(row.role),
                content=row.content,
                created_at=row.created_at,
                evidence=row.evidence,
                channel=Channel(row.channel),
                interrupted=row.interrupted,
            )
            for row in result.scalars().all()
        ]
