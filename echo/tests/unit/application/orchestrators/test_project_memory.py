"""Uses real ProjectService and MemoryService backed by fakes, matching
tests/unit/application/orchestrators/test_news_intelligence.py's own
pattern.
"""

from datetime import UTC, datetime

from application.orchestrators.project_memory import ProjectMemoryOrchestrator
from core.time import FakeClock
from domains.memory.models import MemoryStatus
from domains.memory.service import MemoryService
from domains.projects.service import ProjectService
from tests.unit.domains.memory.fakes import FakeAuditRepository as FakeMemoryAuditRepository
from tests.unit.domains.memory.fakes import FakeMemoryRepository
from tests.unit.domains.projects.fakes import FakeAuditRepository as FakeProjectsAuditRepository
from tests.unit.domains.projects.fakes import FakeProjectRepository


def _orchestrator(
    clock: FakeClock,
) -> tuple[ProjectMemoryOrchestrator, ProjectService, MemoryService]:
    projects = ProjectService(FakeProjectRepository(), FakeProjectsAuditRepository(), clock)
    memory = MemoryService(FakeMemoryRepository(), FakeMemoryAuditRepository(), clock)
    return ProjectMemoryOrchestrator(projects, memory), projects, memory


async def test_record_decision_with_memory_creates_both_records() -> None:
    """PROMPT.md Phase 23 implement item 9: "memory integration.\" """
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, projects, memory = _orchestrator(clock)
    project = await projects.create_project("user_1", "Kitchen remodel")

    decision, memory_record = await orchestrator.record_decision_with_memory(
        project.project_id, "Chose quartz over granite", rationale="Better durability"
    )

    assert decision.description == "Chose quartz over granite"
    stored_decisions = await projects.list_decisions_for_project(project.project_id)
    assert decision in stored_decisions

    assert memory_record.user_id == "user_1"
    assert "Kitchen remodel" in memory_record.content
    assert "Chose quartz over granite" in memory_record.content
    assert memory_record.source_type == "project_decision"
    assert memory_record.source_id == decision.decision_id


async def test_record_decision_with_memory_never_auto_confirms() -> None:
    """Every other memory-producing pathway in this codebase only ever
    creates a CANDIDATE — this integration must not be a silent exception."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, projects, _ = _orchestrator(clock)
    project = await projects.create_project("user_1", "Kitchen remodel")

    _, memory_record = await orchestrator.record_decision_with_memory(
        project.project_id, "Chose a contractor"
    )

    assert memory_record.status == MemoryStatus.CANDIDATE
