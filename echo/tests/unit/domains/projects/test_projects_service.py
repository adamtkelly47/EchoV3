from datetime import UTC, datetime

import pytest

from core.time import FakeClock
from domains.projects.errors import (
    BlockerNotFoundError,
    InvalidTaskTransitionError,
    MilestoneNotFoundError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from domains.projects.models import GoalStatus, ProjectStatus, TaskStatus
from domains.projects.service import ProjectService
from tests.unit.domains.projects.fakes import FakeAuditRepository, FakeProjectRepository


def _service(clock: FakeClock | None = None) -> tuple[ProjectService, FakeProjectRepository]:
    repo = FakeProjectRepository()
    service = ProjectService(
        repo, FakeAuditRepository(), clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    )
    return service, repo


async def test_create_project_defaults_to_active() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel", "Full renovation")
    assert project.status == ProjectStatus.ACTIVE
    assert project.name == "Kitchen remodel"


async def test_get_project_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(ProjectNotFoundError):
        await service.get_project("does-not-exist")


async def test_list_projects_for_user_scopes_correctly() -> None:
    service, _ = _service()
    await service.create_project("user_1", "Project A")
    await service.create_project("user_2", "Project B")
    projects = await service.list_projects_for_user("user_1")
    assert [p.name for p in projects] == ["Project A"]


async def test_update_project_status() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    updated = await service.update_project_status(project.project_id, ProjectStatus.ON_HOLD)
    assert updated.status == ProjectStatus.ON_HOLD


async def test_add_document_link_appends_without_replacing() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    first = await service.add_document_link(project.project_id, "https://example.com/plan")
    second = await service.add_document_link(project.project_id, "https://example.com/quote")
    assert first.document_links == ["https://example.com/plan"]
    assert second.document_links == ["https://example.com/plan", "https://example.com/quote"]


async def test_add_goal_and_update_status() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    goal = await service.add_goal(project.project_id, "Finish before the holidays")
    assert goal.status == GoalStatus.OPEN

    updated = await service.update_goal_status(
        goal.goal_id, GoalStatus.ACHIEVED, project.project_id
    )
    assert updated.status == GoalStatus.ACHIEVED


async def test_add_milestone_and_complete() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    milestone = await service.add_milestone(project.project_id, "Demo complete")
    assert milestone.status.value == "pending"

    completed = await service.complete_milestone(milestone.milestone_id)
    assert completed.status.value == "completed"
    assert completed.completed_at is not None


async def test_complete_milestone_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(MilestoneNotFoundError):
        await service.complete_milestone("does-not-exist")


async def test_propose_task_defaults_to_proposed() -> None:
    """PROMPT.md Phase 23 verification 3: every task starts as a
    suggestion, never silently pre-committed."""
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    task = await service.propose_task(project.project_id, "Order cabinets")
    assert task.status == TaskStatus.PROPOSED


async def test_task_lifecycle_follows_valid_transitions() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    task = await service.propose_task(project.project_id, "Order cabinets")

    committed = await service.commit_task(task.task_id)
    assert committed.status == TaskStatus.COMMITTED

    started = await service.start_task(task.task_id)
    assert started.status == TaskStatus.IN_PROGRESS

    done = await service.complete_task(task.task_id)
    assert done.status == TaskStatus.DONE


async def test_task_cannot_skip_from_proposed_to_in_progress() -> None:
    """PROMPT.md Phase 23 verification 3: the assistant distinguishes
    proposed from committed tasks — enforced here as a real, rejected
    transition, not just a UI convention."""
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    task = await service.propose_task(project.project_id, "Order cabinets")

    with pytest.raises(InvalidTaskTransitionError):
        await service.start_task(task.task_id)


async def test_task_cannot_skip_from_proposed_to_done() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    task = await service.propose_task(project.project_id, "Order cabinets")

    with pytest.raises(InvalidTaskTransitionError):
        await service.complete_task(task.task_id)


async def test_done_task_cannot_be_cancelled() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    task = await service.propose_task(project.project_id, "Order cabinets")
    await service.commit_task(task.task_id)
    await service.start_task(task.task_id)
    await service.complete_task(task.task_id)

    with pytest.raises(InvalidTaskTransitionError):
        await service.cancel_task(task.task_id)


async def test_transition_task_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(TaskNotFoundError):
        await service.commit_task("does-not-exist")


async def test_record_decision_is_append_only() -> None:
    """PROMPT.md Phase 23 verification 2: "decisions are historically
    traceable" — recording a second decision never replaces the first."""
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    first = await service.record_decision(project.project_id, "Chose quartz over granite")
    second = await service.record_decision(
        project.project_id, "Chose a contractor", rationale="Best references"
    )

    decisions = await service.list_decisions_for_project(project.project_id)
    assert {d.decision_id for d in decisions} == {first.decision_id, second.decision_id}
    assert second.rationale == "Best references"


async def test_raise_and_resolve_blocker() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    blocker = await service.raise_blocker(project.project_id, "Waiting on permit")
    assert blocker.status.value == "open"

    resolved = await service.resolve_blocker(blocker.blocker_id)
    assert resolved.status.value == "resolved"
    assert resolved.resolved_at is not None


async def test_resolve_blocker_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(BlockerNotFoundError):
        await service.resolve_blocker("does-not-exist")


async def test_record_status_update() -> None:
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    update = await service.record_status_update(project.project_id, "Demo complete")
    listed = await service.list_status_updates_for_project(project.project_id)
    assert listed == [update]


async def test_get_project_status_summary_reflects_real_state() -> None:
    """PROMPT.md Phase 23 implement item 1 / verification 1."""
    service, _ = _service()
    project = await service.create_project("user_1", "Kitchen remodel")
    task = await service.propose_task(project.project_id, "Order cabinets")
    await service.commit_task(task.task_id)
    await service.raise_blocker(project.project_id, "Waiting on permit")

    summary = await service.get_project_status_summary(project.project_id)

    assert summary.total_tasks == 1
    assert summary.committed_tasks == 1
    assert summary.open_blockers == 1
