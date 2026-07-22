from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.conversation.repository import PostgresConversationRepository
from domains.conversation.schemas import Channel, ConversationSession, Message, MessageRole


async def test_save_and_get_session(db_session: AsyncSession) -> None:
    repo = PostgresConversationRepository(db_session)
    session = ConversationSession(user_id="user_1", started_at=datetime(2026, 1, 1, tzinfo=UTC))

    await repo.save_session(session)
    restored = await repo.get_session(session.session_id)

    assert restored is not None
    assert restored.user_id == "user_1"
    assert restored.status == "active"


async def test_messages_round_trip_with_evidence(db_session: AsyncSession) -> None:
    repo = PostgresConversationRepository(db_session)
    session = ConversationSession(user_id="user_1", started_at=datetime(2026, 1, 1, tzinfo=UTC))
    await repo.save_session(session)

    user_message = Message(
        session_id=session.session_id,
        role=MessageRole.USER,
        content="what time is it?",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    assistant_message = Message(
        session_id=session.session_id,
        role=MessageRole.ASSISTANT,
        content="it's noon",
        created_at=datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC),
        evidence={"current_time": {"iso_timestamp": "2026-01-01T12:00:00+00:00"}},
    )
    await repo.save_message(user_message)
    await repo.save_message(assistant_message)

    history = await repo.get_messages(session.session_id)
    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert history[1].evidence == {"current_time": {"iso_timestamp": "2026-01-01T12:00:00+00:00"}}


async def test_message_channel_and_interrupted_round_trip(db_session: AsyncSession) -> None:
    """PROMPT.md Phase 26 implement items 1 and 4: "input channel
    abstraction" and "interruption handling contract" — proven against
    real Postgres, not just the in-memory fake."""
    repo = PostgresConversationRepository(db_session)
    session = ConversationSession(user_id="user_1", started_at=datetime(2026, 1, 1, tzinfo=UTC))
    await repo.save_session(session)

    voice_message = Message(
        session_id=session.session_id,
        role=MessageRole.ASSISTANT,
        content="partial reply",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        channel=Channel.VOICE,
        interrupted=True,
    )
    await repo.save_message(voice_message)

    history = await repo.get_messages(session.session_id)
    assert history[0].channel == Channel.VOICE
    assert history[0].interrupted is True


async def test_message_channel_defaults_to_text(db_session: AsyncSession) -> None:
    repo = PostgresConversationRepository(db_session)
    session = ConversationSession(user_id="user_1", started_at=datetime(2026, 1, 1, tzinfo=UTC))
    await repo.save_session(session)

    message = Message(
        session_id=session.session_id,
        role=MessageRole.USER,
        content="hello",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await repo.save_message(message)

    history = await repo.get_messages(session.session_id)
    assert history[0].channel == Channel.TEXT
    assert history[0].interrupted is False


async def test_list_recent_sessions_for_user_orders_most_recent_first(
    db_session: AsyncSession,
) -> None:
    """PROMPT.md Phase 22 implement item 5: "conversation" (dashboard
    card)."""
    repo = PostgresConversationRepository(db_session)
    older = ConversationSession(
        user_id="dashboard_test_user", started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    newer = ConversationSession(
        user_id="dashboard_test_user", started_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    other_user = ConversationSession(
        user_id="other_dashboard_test_user", started_at=datetime(2026, 1, 3, tzinfo=UTC)
    )
    await repo.save_session(older)
    await repo.save_session(newer)
    await repo.save_session(other_user)

    recent = await repo.list_recent_sessions_for_user("dashboard_test_user")

    assert [s.session_id for s in recent] == [newer.session_id, older.session_id]
