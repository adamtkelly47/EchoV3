from datetime import UTC, datetime

import pytest

from core.time import FakeClock
from domains.conversation.errors import SessionNotFoundError
from domains.conversation.schemas import MessageRole
from domains.conversation.service import ConversationService
from tests.unit.domains.conversation.fakes import FakeConversationRepository


def _service() -> ConversationService:
    return ConversationService(
        FakeConversationRepository(), FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    )


async def test_start_session_creates_a_session() -> None:
    service = _service()
    session = await service.start_session("user_1")
    assert session.user_id == "user_1"
    assert session.status == "active"


async def test_append_message_requires_an_existing_session() -> None:
    service = _service()
    with pytest.raises(SessionNotFoundError):
        await service.append_message("does-not-exist", role=MessageRole.USER, content="hi")


async def test_history_returns_messages_in_order() -> None:
    service = _service()
    session = await service.start_session("user_1")
    await service.append_message(session.session_id, role=MessageRole.USER, content="hi")
    await service.append_message(
        session.session_id, role=MessageRole.ASSISTANT, content="hello there"
    )

    history = await service.get_history(session.session_id)
    assert [m.content for m in history] == ["hi", "hello there"]


async def test_evidence_is_preserved_on_assistant_messages() -> None:
    service = _service()
    session = await service.start_session("user_1")
    message = await service.append_message(
        session.session_id,
        role=MessageRole.ASSISTANT,
        content="it's noon",
        evidence={"current_time": {"iso_timestamp": "2026-01-01T12:00:00+00:00"}},
    )
    assert message.evidence == {"current_time": {"iso_timestamp": "2026-01-01T12:00:00+00:00"}}
