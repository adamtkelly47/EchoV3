"""PROMPT.md Phase 26: "prepare interfaces for voice without allowing
voice logic to diverge from chat." These tests prove the channel
abstraction, response-chunk events, interruption contract, and
transcript-stream-to-chat delegation all work through the real
ConversationOrchestrator, backed by fakes — the same pattern
test_conversation_orchestrator.py already established for Phase 8.
"""

from datetime import UTC, datetime

from application.orchestrators.conversation import ConversationOrchestrator, _TimeNeedDecision
from core.time import FakeClock
from domains.capabilities.service import CapabilityExecutor, CapabilityRegistry
from domains.conversation.events import TranscriptChunkPayload
from domains.conversation.schemas import Channel, MessageRole
from domains.conversation.service import ConversationService
from tests.unit.application.orchestrators.fakes import FakeModelGateway
from tests.unit.domains.capabilities.fakes import FakeToolCallRepository
from tests.unit.domains.conversation.fakes import FakeConversationRepository


class _FakeInterruptSignal:
    def __init__(self, interrupt_after: int) -> None:
        self._interrupt_after = interrupt_after
        self._checks = 0

    async def is_interrupted(self) -> bool:
        self._checks += 1
        return self._checks > self._interrupt_after


def _orchestrator(clock: FakeClock) -> tuple[ConversationOrchestrator, ConversationService]:
    conversations = ConversationService(FakeConversationRepository(), clock)
    registry = CapabilityRegistry()
    executor = CapabilityExecutor(registry, FakeToolCallRepository(), clock)
    gateway = FakeModelGateway(structured_decision=_TimeNeedDecision(needs_current_time=False))
    orchestrator = ConversationOrchestrator(conversations, executor, gateway, clock)
    return orchestrator, conversations


async def test_handle_message_persists_the_real_channel() -> None:
    """PROMPT.md Phase 26 implement item 1: "input channel abstraction.\" """
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations = _orchestrator(clock)
    session = await conversations.start_session("user_1")

    reply = await orchestrator.handle_message(
        session.session_id, "hello there", channel=Channel.VOICE
    )
    assert reply.channel == Channel.VOICE

    history = await conversations.get_history(session.session_id)
    assert all(m.channel == Channel.VOICE for m in history)


async def test_handle_message_defaults_to_text_channel() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations = _orchestrator(clock)
    session = await conversations.start_session("user_1")

    reply = await orchestrator.handle_message(session.session_id, "hello there")
    assert reply.channel == Channel.TEXT


async def test_stream_without_interruption_completes_normally() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations = _orchestrator(clock)
    session = await conversations.start_session("user_1")

    events = [e async for e in orchestrator.handle_message_stream(session.session_id, "a b c d e")]
    assert events[-1].payload.is_final is True
    assert events[-1].payload.interrupted is False

    history = await conversations.get_history(session.session_id)
    assert history[-1].interrupted is False


async def test_interruption_stops_the_stream_early_and_marks_the_message() -> None:
    """PROMPT.md Phase 26 implement item 4: "interruption handling
    contract.\" """
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations = _orchestrator(clock)
    session = await conversations.start_session("user_1")
    interrupt = _FakeInterruptSignal(interrupt_after=2)

    events = [
        e
        async for e in orchestrator.handle_message_stream(
            session.session_id, "a b c d e f g", interrupt=interrupt
        )
    ]
    non_final = [e for e in events if not e.payload.is_final]
    assert len(non_final) == 2  # stopped after exactly 2 chunks
    assert events[-1].payload.interrupted is True
    assert events[-1].payload.is_final is True

    history = await conversations.get_history(session.session_id)
    assistant_message = history[-1]
    assert assistant_message.interrupted is True
    assert assistant_message.content == "".join(e.payload.text for e in non_final)


async def test_transcript_stream_delegates_to_handle_message_stream_once_final() -> None:
    """PROMPT.md Phase 26 implement item 2: "streaming transcript
    events" — and the phase's own objective: voice input funnels into
    the exact same pipeline text input already uses."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, conversations = _orchestrator(clock)
    session = await conversations.start_session("user_1")

    async def transcript_chunks():
        yield TranscriptChunkPayload(session_id=session.session_id, text="hel", is_final=False)
        yield TranscriptChunkPayload(session_id=session.session_id, text="hello", is_final=False)
        yield TranscriptChunkPayload(
            session_id=session.session_id, text="hello there", is_final=True
        )

    events = [
        e
        async for e in orchestrator.handle_transcript_stream(
            session.session_id, transcript_chunks()
        )
    ]
    assert events[-1].payload.is_final is True

    history = await conversations.get_history(session.session_id)
    assert history[0].role == MessageRole.USER
    assert history[0].content == "hello there"  # the FINAL transcript, not a partial one
    assert history[0].channel == Channel.VOICE
    assert history[-1].channel == Channel.VOICE
