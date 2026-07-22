from __future__ import annotations

from typing import Any

from core.time import Clock
from domains.conversation.errors import SessionNotFoundError
from domains.conversation.repository import ConversationRepository
from domains.conversation.schemas import Channel, ConversationSession, Message, MessageRole


class ConversationService:
    def __init__(self, repository: ConversationRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def start_session(self, user_id: str) -> ConversationSession:
        session = ConversationSession(user_id=user_id, started_at=self._clock.now_utc())
        await self._repository.save_session(session)
        return session

    async def append_message(
        self,
        session_id: str,
        *,
        role: MessageRole,
        content: str,
        evidence: dict[str, Any] | None = None,
        channel: Channel = Channel.TEXT,
        interrupted: bool = False,
    ) -> Message:
        if await self._repository.get_session(session_id) is None:
            raise SessionNotFoundError(f"no conversation session {session_id!r}")
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            created_at=self._clock.now_utc(),
            evidence=evidence,
            channel=channel,
            interrupted=interrupted,
        )
        await self._repository.save_message(message)
        return message

    async def get_history(self, session_id: str) -> list[Message]:
        if await self._repository.get_session(session_id) is None:
            raise SessionNotFoundError(f"no conversation session {session_id!r}")
        return await self._repository.get_messages(session_id)

    async def list_recent_sessions(
        self, user_id: str, *, limit: int = 5
    ) -> list[ConversationSession]:
        """PROMPT.md Phase 22 implement item 5: "conversation" (dashboard
        card)."""
        return await self._repository.list_recent_sessions_for_user(user_id, limit=limit)
