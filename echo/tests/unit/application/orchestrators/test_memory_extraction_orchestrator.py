from datetime import UTC, datetime

from application.orchestrators.memory_extraction import (
    ExtractedMemoryCandidate,
    MemoryExtractionOrchestrator,
    _DurableFactGateDecision,
)
from core.time import FakeClock
from domains.memory.models import MemoryStatus
from domains.memory.service import MemoryService
from tests.unit.application.orchestrators.fakes import FakeSequentialModelGateway
from tests.unit.domains.memory.fakes import FakeAuditRepository, FakeMemoryRepository


def _memory_service() -> MemoryService:
    return MemoryService(
        FakeMemoryRepository(), FakeAuditRepository(), FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    )


async def test_durable_fact_is_recorded_as_a_candidate_not_confirmed() -> None:
    gateway = FakeSequentialModelGateway(
        structured_decisions=[
            _DurableFactGateDecision(has_durable_fact=True),
            ExtractedMemoryCandidate(
                subject_key="user.favorite_color",
                content="The user's favorite color is blue.",
                confidence=0.9,
            ),
        ]
    )
    memory = _memory_service()
    orchestrator = MemoryExtractionOrchestrator(memory, gateway)

    recorded = await orchestrator.extract_and_record(
        "My favorite color is blue.",
        user_id="user_1",
        source_type="conversation",
        source_id="msg_1",
    )

    assert len(recorded) == 1
    assert recorded[0].status == MemoryStatus.CANDIDATE
    assert recorded[0].subject_key == "user.favorite_color"
    assert recorded[0].source_id == "msg_1"


async def test_non_fact_message_records_nothing() -> None:
    gateway = FakeSequentialModelGateway(
        structured_decisions=[_DurableFactGateDecision(has_durable_fact=False)]
    )
    memory = _memory_service()
    orchestrator = MemoryExtractionOrchestrator(memory, gateway)

    recorded = await orchestrator.extract_and_record(
        "Tell me a joke about cats.",
        user_id="user_1",
        source_type="conversation",
        source_id="msg_1",
    )

    assert recorded == []
    assert await memory.list_all_for_user("user_1") == []


async def test_gate_decision_short_circuits_the_extraction_call() -> None:
    """Only one structured call is configured (the gate) — if the
    orchestrator called extraction anyway despite a False gate decision,
    FakeSequentialModelGateway's queue would be empty and this would fail
    with an AssertionError rather than silently passing."""
    gateway = FakeSequentialModelGateway(
        structured_decisions=[_DurableFactGateDecision(has_durable_fact=False)]
    )
    orchestrator = MemoryExtractionOrchestrator(_memory_service(), gateway)

    await orchestrator.extract_and_record(
        "What time is it?", user_id="user_1", source_type="conversation", source_id="msg_1"
    )

    assert len(gateway.structured_calls) == 1
