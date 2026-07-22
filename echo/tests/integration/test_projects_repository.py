from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.projects.models import BlockerStatus, GoalStatus, MilestoneStatus, TaskStatus
from domains.projects.repository import PostgresProjectRepository
from domains.projects.schemas import Blocker, Decision, Goal, Milestone, Project, StatusUpdate, Task


async def test_project_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    project = Project(
        user_id="user_1",
        name="Kitchen remodel",
        description="Full renovation",
        document_links=["https://example.com/plan"],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_project(project)

    restored = await repo.get_project(project.project_id)
    assert restored is not None
    assert restored.name == "Kitchen remodel"
    assert restored.document_links == ["https://example.com/plan"]


async def test_project_save_upserts_by_project_id(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    project = Project(
        user_id="user_1",
        name="Kitchen remodel",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_project(project)

    updated = project.model_copy(
        update={"name": "Kitchen remodel v2", "updated_at": datetime(2026, 1, 2, tzinfo=UTC)}
    )
    await repo.save_project(updated)

    restored = await repo.get_project(project.project_id)
    assert restored is not None
    assert restored.name == "Kitchen remodel v2"


async def test_list_projects_for_user_scopes_correctly(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    mine = Project(
        user_id="projects_repo_test_user",
        name="Mine",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    other = Project(
        user_id="projects_repo_test_other_user",
        name="Not mine",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_project(mine)
    await repo.save_project(other)

    matches = await repo.list_projects_for_user("projects_repo_test_user")
    assert [p.project_id for p in matches] == [mine.project_id]


async def test_goal_save_and_list_for_project(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    goal = Goal(
        project_id="project_1",
        description="Finish before the holidays",
        status=GoalStatus.OPEN,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_goal(goal)

    listed = await repo.list_goals_for_project("project_1")
    assert len(listed) == 1
    assert listed[0].description == "Finish before the holidays"


async def test_milestone_save_get_and_list(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    milestone = Milestone(
        project_id="project_1",
        name="Demo complete",
        due_date=datetime(2026, 2, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_milestone(milestone)

    fetched = await repo.get_milestone(milestone.milestone_id)
    assert fetched is not None
    assert fetched.status == MilestoneStatus.PENDING

    listed = await repo.list_milestones_for_project("project_1")
    assert len(listed) == 1


async def test_task_save_get_and_list(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    task = Task(
        project_id="project_1",
        description="Order cabinets",
        status=TaskStatus.PROPOSED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_task(task)

    fetched = await repo.get_task(task.task_id)
    assert fetched is not None
    assert fetched.status == TaskStatus.PROPOSED

    listed = await repo.list_tasks_for_project("project_1")
    assert len(listed) == 1


async def test_decision_save_is_append_only_and_round_trips(db_session: AsyncSession) -> None:
    """PROMPT.md Phase 23 verification 2: "decisions are historically
    traceable" — proven against real Postgres, not just the in-memory fake."""
    repo = PostgresProjectRepository(db_session)
    first = Decision(
        project_id="project_1",
        description="Chose quartz over granite",
        decided_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = Decision(
        project_id="project_1",
        description="Chose a contractor",
        rationale="Best references",
        decided_at=datetime(2026, 1, 5, tzinfo=UTC),
    )
    await repo.save_decision(first)
    await repo.save_decision(second)

    listed = await repo.list_decisions_for_project("project_1")
    assert {d.decision_id for d in listed} == {first.decision_id, second.decision_id}


async def test_blocker_save_get_and_resolve(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    blocker = Blocker(
        project_id="project_1",
        description="Waiting on permit",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_blocker(blocker)

    resolved = blocker.model_copy(
        update={"status": BlockerStatus.RESOLVED, "resolved_at": datetime(2026, 1, 5, tzinfo=UTC)}
    )
    await repo.save_blocker(resolved)

    fetched = await repo.get_blocker(blocker.blocker_id)
    assert fetched is not None
    assert fetched.status == BlockerStatus.RESOLVED

    listed = await repo.list_blockers_for_project("project_1")
    assert len(listed) == 1  # upserted, not duplicated


async def test_status_update_save_and_list(db_session: AsyncSession) -> None:
    repo = PostgresProjectRepository(db_session)
    update = StatusUpdate(
        project_id="project_1", summary="Demo complete", created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    await repo.save_status_update(update)

    listed = await repo.list_status_updates_for_project("project_1")
    assert len(listed) == 1
    assert listed[0].summary == "Demo complete"
