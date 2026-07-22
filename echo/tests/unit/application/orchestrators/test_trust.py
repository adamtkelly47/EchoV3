"""Uses real Memory/System services backed by fakes, matching
tests/unit/application/orchestrators/test_project_memory.py's own pattern.
"""

from datetime import UTC, datetime

from application.orchestrators.trust import TrustOrchestrator
from core.time import FakeClock
from domains.memory.service import MemoryService
from domains.system.service import SystemService
from tests.unit.domains.memory.fakes import FakeAuditRepository as FakeMemoryAuditRepository
from tests.unit.domains.memory.fakes import FakeMemoryRepository
from tests.unit.domains.system.fakes import FakeAuditRepository as FakeSystemAuditRepository
from tests.unit.domains.system.fakes import FakeSystemRepository


def _orchestrator(clock: FakeClock) -> tuple[TrustOrchestrator, MemoryService, SystemService]:
    memory = MemoryService(FakeMemoryRepository(), FakeMemoryAuditRepository(), clock)
    system = SystemService(FakeSystemRepository(), FakeSystemAuditRepository(), clock)
    return TrustOrchestrator(memory, system), memory, system


async def test_record_user_correction_supersedes_the_memory_with_user_correction_source_type() -> (
    None
):
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, memory, _ = _orchestrator(clock)
    original = await memory.record_candidate(
        user_id="user_1",
        subject_key="favorite_color",
        content="blue",
        confidence=0.8,
        source_type="conversation",
        source_id="conv_1",
    )
    await memory.confirm(original.memory_id)

    corrected, _case = await orchestrator.record_user_correction(
        original.memory_id, content="green", confidence=0.95
    )
    assert corrected.content == "green"
    assert corrected.source_type == "user_correction"
    assert corrected.supersedes_memory_id == original.memory_id


async def test_record_user_correction_creates_a_regression_case_from_the_old_and_new_content() -> (
    None
):
    """PROMPT.md Phase 25: "Create regression datasets from corrected
    failures.\" """
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, memory, system = _orchestrator(clock)
    original = await memory.record_candidate(
        user_id="user_1",
        subject_key="favorite_color",
        content="blue",
        confidence=0.8,
        source_type="conversation",
        source_id="conv_1",
    )
    await memory.confirm(original.memory_id)

    _corrected, case = await orchestrator.record_user_correction(
        original.memory_id, content="green", confidence=0.95
    )
    assert case.source_type == "user_correction"
    assert case.incorrect_output == "blue"
    assert case.corrected_output == "green"

    cases = await system.list_regression_cases()
    assert cases == [case]
