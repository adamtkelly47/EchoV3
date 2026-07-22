"""Proves PROMPT.md Phase 8's verification criteria directly: the user can
ask for the current time, the system calls the real current_time
capability (not the model's own knowledge), the response includes the
actual time from the platform clock, and the model is never left to guess
a time on its own.
"""

from datetime import UTC, datetime

from pydantic import BaseModel

from application.capabilities.current_time import build_current_time_capability
from application.orchestrators.conversation import (
    _RESPONSE_TEMPERATURE,
    ConversationOrchestrator,
    _TimeNeedDecision,
)
from core.time import FakeClock
from domains.capabilities.service import CapabilityExecutor, CapabilityRegistry
from domains.conversation.schemas import MessageRole
from domains.conversation.service import ConversationService
from tests.unit.application.orchestrators.fakes import FakeModelGateway
from tests.unit.domains.capabilities.fakes import FakeToolCallRepository
from tests.unit.domains.conversation.fakes import FakeConversationRepository


class _Other(BaseModel):
    pass


def _build(
    *, needs_time: bool, clock: FakeClock
) -> tuple[ConversationOrchestrator, ConversationService, FakeModelGateway]:
    conversations = ConversationService(FakeConversationRepository(), clock)
    registry = CapabilityRegistry()
    registry.register(build_current_time_capability(clock))
    executor = CapabilityExecutor(registry, FakeToolCallRepository(), clock)
    gateway = FakeModelGateway(structured_decision=_TimeNeedDecision(needs_current_time=needs_time))
    orchestrator = ConversationOrchestrator(conversations, executor, gateway, clock)
    return orchestrator, conversations, gateway


async def test_time_question_triggers_the_capability_and_includes_the_real_time() -> None:
    clock = FakeClock(datetime(2026, 3, 15, 9, 30, 0, tzinfo=UTC))
    orchestrator, conversations, gateway = _build(needs_time=True, clock=clock)
    session = await conversations.start_session("user_1")

    reply = await orchestrator.handle_message(session.session_id, "what time is it?")

    # verification criterion: response includes actual current time
    assert "2026-03-15T09:30:00+00:00" in reply.content
    # verification criterion: the system called the clock capability, not the model's memory
    assert reply.evidence is not None
    assert reply.evidence["current_time"]["iso_timestamp"] == "2026-03-15T09:30:00+00:00"


async def test_model_is_given_the_real_time_not_left_to_assume_one() -> None:
    """The fake gateway's `generate` just echoes the prompt it received —
    so if the real time appears in what it echoed, the orchestrator must
    have injected it into the prompt itself, rather than the model
    inventing a time from its own session context."""
    clock = FakeClock(datetime(2099, 12, 31, 23, 59, 59, tzinfo=UTC))
    orchestrator, conversations, gateway = _build(needs_time=True, clock=clock)
    session = await conversations.start_session("user_1")

    await orchestrator.handle_message(session.session_id, "what's today's date?")

    assert len(gateway.generate_calls) == 1
    assert "2099-12-31T23:59:59+00:00" in gateway.generate_calls[0].prompt
    assert "SYSTEM FACT" in gateway.generate_calls[0].prompt
    # Docs/DECISION_LOG.md Phase 8: evidence-grounded responses use low,
    # non-default sampling temperature — the model's highest-probability
    # completion for a "you already have this fact" prompt must be tested
    # deterministically, not left to default randomness.
    assert gateway.generate_calls[0].temperature == _RESPONSE_TEMPERATURE


async def test_non_grounded_response_does_not_pin_temperature() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations, gateway = _build(needs_time=False, clock=clock)
    session = await conversations.start_session("user_1")

    await orchestrator.handle_message(session.session_id, "tell me a joke")

    assert gateway.generate_calls[0].temperature is None


async def test_non_time_question_does_not_call_the_capability() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations, gateway = _build(needs_time=False, clock=clock)
    session = await conversations.start_session("user_1")

    reply = await orchestrator.handle_message(session.session_id, "tell me a joke")

    assert reply.evidence is None
    assert "2026-01-01" not in gateway.generate_calls[0].prompt


async def test_conversation_history_persists_both_turns() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations, _ = _build(needs_time=True, clock=clock)
    session = await conversations.start_session("user_1")

    await orchestrator.handle_message(session.session_id, "what time is it?")

    history = await conversations.get_history(session.session_id)
    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]


async def test_streaming_variant_persists_the_full_accumulated_response() -> None:
    clock = FakeClock(datetime(2026, 6, 1, 8, 0, 0, tzinfo=UTC))
    orchestrator, conversations, _ = _build(needs_time=True, clock=clock)
    session = await conversations.start_session("user_1")

    events = [event async for event in orchestrator.handle_message_stream(session.session_id, "hi")]
    # PROMPT.md Phase 26 implement item 3: every yielded chunk is a real
    # ResponseChunkEvent, not a bare string — the final one always marks
    # is_final=True.
    assert len(events) > 1  # genuinely streamed as multiple pieces
    assert events[-1].payload.is_final is True
    assert all(not e.payload.is_final for e in events[:-1])

    history = await conversations.get_history(session.session_id)
    assistant_message = history[-1]
    assert assistant_message.role == MessageRole.ASSISTANT
    assert assistant_message.content == "".join(e.payload.text for e in events[:-1])
    assert assistant_message.interrupted is False
