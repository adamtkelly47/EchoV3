from datetime import UTC, datetime

from domains.projects.models import BlockerStatus, MilestoneStatus, ProjectStatus, TaskStatus
from domains.projects.policies import compute_project_status_summary, is_milestone_overdue
from domains.projects.schemas import Blocker, Decision, Milestone, Project, StatusUpdate, Task


def _project(**overrides: object) -> Project:
    defaults: dict[str, object] = {
        "user_id": "user_1",
        "name": "Kitchen remodel",
        "status": ProjectStatus.ACTIVE,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Project(**defaults)  # type: ignore[arg-type]


def _milestone(**overrides: object) -> Milestone:
    defaults: dict[str, object] = {
        "project_id": "project_1",
        "name": "Demo complete",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Milestone(**defaults)  # type: ignore[arg-type]


def _task(**overrides: object) -> Task:
    defaults: dict[str, object] = {
        "project_id": "project_1",
        "description": "Order cabinets",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Task(**defaults)  # type: ignore[arg-type]


def test_is_milestone_overdue_true_when_due_date_passed_and_still_pending() -> None:
    milestone = _milestone(due_date=datetime(2026, 1, 1, tzinfo=UTC))
    assert is_milestone_overdue(milestone, datetime(2026, 2, 1, tzinfo=UTC)) is True


def test_is_milestone_overdue_false_when_completed() -> None:
    milestone = _milestone(
        due_date=datetime(2026, 1, 1, tzinfo=UTC), status=MilestoneStatus.COMPLETED
    )
    assert is_milestone_overdue(milestone, datetime(2026, 2, 1, tzinfo=UTC)) is False


def test_is_milestone_overdue_false_when_no_due_date() -> None:
    milestone = _milestone(due_date=None)
    assert is_milestone_overdue(milestone, datetime(2026, 2, 1, tzinfo=UTC)) is False


def test_compute_project_status_summary_counts_tasks_by_status() -> None:
    """PROMPT.md Phase 23 verification 1: "project status is based on
    stored facts" — every count here is a real tally, not an assertion."""
    project = _project()
    tasks = [
        _task(status=TaskStatus.PROPOSED),
        _task(status=TaskStatus.COMMITTED),
        _task(status=TaskStatus.COMMITTED),
        _task(status=TaskStatus.IN_PROGRESS),
        _task(status=TaskStatus.DONE),
    ]
    summary = compute_project_status_summary(
        project, tasks, [], [], [], [], datetime(2026, 1, 15, tzinfo=UTC)
    )
    assert summary.total_tasks == 5
    assert summary.proposed_tasks == 1
    assert summary.committed_tasks == 2
    assert summary.in_progress_tasks == 1
    assert summary.done_tasks == 1


def test_compute_project_status_summary_counts_open_blockers_only() -> None:
    project = _project()
    blockers = [
        Blocker(
            project_id="project_1",
            description="Waiting on permit",
            status=BlockerStatus.OPEN,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        Blocker(
            project_id="project_1",
            description="Contractor unavailable",
            status=BlockerStatus.RESOLVED,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            resolved_at=datetime(2026, 1, 5, tzinfo=UTC),
        ),
    ]
    summary = compute_project_status_summary(
        project, [], [], blockers, [], [], datetime(2026, 1, 15, tzinfo=UTC)
    )
    assert summary.open_blockers == 1


def test_compute_project_status_summary_finds_next_and_overdue_milestones() -> None:
    project = _project()
    overdue = _milestone(
        milestone_id="m_overdue", name="Permit approved", due_date=datetime(2026, 1, 1, tzinfo=UTC)
    )
    next_up = _milestone(
        milestone_id="m_next", name="Demo complete", due_date=datetime(2026, 2, 1, tzinfo=UTC)
    )
    later = _milestone(
        milestone_id="m_later", name="Final inspection", due_date=datetime(2026, 3, 1, tzinfo=UTC)
    )
    completed = _milestone(
        milestone_id="m_done",
        name="Design finalized",
        due_date=datetime(2026, 1, 1, tzinfo=UTC),
        status=MilestoneStatus.COMPLETED,
    )
    summary = compute_project_status_summary(
        project,
        [],
        [overdue, next_up, later, completed],
        [],
        [],
        [],
        datetime(2026, 1, 15, tzinfo=UTC),
    )
    assert summary.overdue_milestones == [overdue]
    assert summary.next_milestone is not None
    assert summary.next_milestone.milestone_id == "m_next"


def test_compute_project_status_summary_latest_status_update_and_decision() -> None:
    project = _project()
    status_updates = [
        StatusUpdate(
            project_id="project_1",
            summary="Started demo",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        StatusUpdate(
            project_id="project_1",
            summary="Demo complete, cabinets ordered",
            created_at=datetime(2026, 1, 10, tzinfo=UTC),
        ),
    ]
    decisions = [
        Decision(
            project_id="project_1",
            description="Chose quartz over granite",
            decided_at=datetime(2026, 1, 3, tzinfo=UTC),
        ),
        Decision(
            project_id="project_1",
            description="Chose a contractor",
            decided_at=datetime(2026, 1, 8, tzinfo=UTC),
        ),
    ]
    summary = compute_project_status_summary(
        project, [], [], [], status_updates, decisions, datetime(2026, 1, 15, tzinfo=UTC)
    )
    assert summary.latest_status_update is not None
    assert summary.latest_status_update.summary == "Demo complete, cabinets ordered"
    assert summary.latest_decision is not None
    assert summary.latest_decision.description == "Chose a contractor"


def test_compute_project_status_summary_none_when_no_history() -> None:
    project = _project()
    summary = compute_project_status_summary(
        project, [], [], [], [], [], datetime(2026, 1, 15, tzinfo=UTC)
    )
    assert summary.latest_status_update is None
    assert summary.latest_decision is None
    assert summary.next_milestone is None
    assert summary.overdue_milestones == []
