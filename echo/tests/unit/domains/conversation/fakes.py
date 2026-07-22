from __future__ import annotations

from domains.conversation.schemas import ConversationSession, Message


class FakeConversationRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, ConversationSession] = {}
        self.messages: dict[str, list[Message]] = {}

    async def save_session(self, session: ConversationSession) -> None:
        self.sessions[session.session_id] = session
        self.messages.setdefault(session.session_id, [])

    async def get_session(self, session_id: str) -> ConversationSession | None:
        return self.sessions.get(session_id)

    async def list_recent_sessions_for_user(
        self, user_id: str, *, limit: int = 5
    ) -> list[ConversationSession]:
        matches = sorted(
            (s for s in self.sessions.values() if s.user_id == user_id),
            key=lambda s: s.started_at,
            reverse=True,
        )
        return matches[:limit]

    async def save_message(self, message: Message) -> None:
        self.messages.setdefault(message.session_id, []).append(message)

    async def get_messages(self, session_id: str) -> list[Message]:
        return list(self.messages.get(session_id, []))
