"""Projects owns its own persistence (Docs/DOMAIN_OWNERSHIP.md: "Projects
repositories own: projects, milestones, dependencies, status, history"), so
the ORM tables live here rather than under infrastructure/database/tables/,
matching the Approvals/Calendar/Portfolio/Research precedent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.projects.models import (
    BlockerStatus,
    GoalStatus,
    MilestoneStatus,
    ProjectStatus,
    TaskStatus,
)
from domains.projects.schemas import (
    Blocker,
    Decision,
    Goal,
    Milestone,
    Project,
    StatusUpdate,
    Task,
)
from infrastructure.database.base import Base


class ProjectRow(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    document_links: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GoalRow(Base):
    __tablename__ = "project_goals"

    goal_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MilestoneRow(Base):
    __tablename__ = "project_milestones"

    milestone_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskRow(Base):
    __tablename__ = "project_tasks"

    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    milestone_id: Mapped[str | None] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionRow(Base):
    __tablename__ = "project_decisions"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    rationale: Mapped[str | None] = mapped_column(String)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_context: Mapped[str | None] = mapped_column(String)


class BlockerRow(Base):
    __tablename__ = "project_blockers"

    blocker_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StatusUpdateRow(Base):
    __tablename__ = "project_status_updates"

    status_update_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    summary: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _row_to_project(row: ProjectRow) -> Project:
    return Project(
        project_id=row.project_id,
        user_id=row.user_id,
        name=row.name,
        description=row.description,
        status=ProjectStatus(row.status),
        document_links=list(row.document_links),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_goal(row: GoalRow) -> Goal:
    return Goal(
        goal_id=row.goal_id,
        project_id=row.project_id,
        description=row.description,
        status=GoalStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_milestone(row: MilestoneRow) -> Milestone:
    return Milestone(
        milestone_id=row.milestone_id,
        project_id=row.project_id,
        name=row.name,
        due_date=row.due_date,
        status=MilestoneStatus(row.status),
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def _row_to_task(row: TaskRow) -> Task:
    return Task(
        task_id=row.task_id,
        project_id=row.project_id,
        milestone_id=row.milestone_id,
        description=row.description,
        status=TaskStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_decision(row: DecisionRow) -> Decision:
    return Decision(
        decision_id=row.decision_id,
        project_id=row.project_id,
        description=row.description,
        rationale=row.rationale,
        decided_at=row.decided_at,
        source_context=row.source_context,
    )


def _row_to_blocker(row: BlockerRow) -> Blocker:
    return Blocker(
        blocker_id=row.blocker_id,
        project_id=row.project_id,
        description=row.description,
        status=BlockerStatus(row.status),
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


def _row_to_status_update(row: StatusUpdateRow) -> StatusUpdate:
    return StatusUpdate(
        status_update_id=row.status_update_id,
        project_id=row.project_id,
        summary=row.summary,
        created_at=row.created_at,
    )


class ProjectRepository(Protocol):
    async def save_project(self, project: Project) -> Project: ...
    async def get_project(self, project_id: str) -> Project | None: ...
    async def list_projects_for_user(self, user_id: str) -> list[Project]: ...

    async def save_goal(self, goal: Goal) -> Goal: ...
    async def list_goals_for_project(self, project_id: str) -> list[Goal]: ...

    async def save_milestone(self, milestone: Milestone) -> Milestone: ...
    async def get_milestone(self, milestone_id: str) -> Milestone | None: ...
    async def list_milestones_for_project(self, project_id: str) -> list[Milestone]: ...

    async def save_task(self, task: Task) -> Task: ...
    async def get_task(self, task_id: str) -> Task | None: ...
    async def list_tasks_for_project(self, project_id: str) -> list[Task]: ...

    async def save_decision(self, decision: Decision) -> Decision: ...
    async def list_decisions_for_project(self, project_id: str) -> list[Decision]: ...

    async def save_blocker(self, blocker: Blocker) -> Blocker: ...
    async def get_blocker(self, blocker_id: str) -> Blocker | None: ...
    async def list_blockers_for_project(self, project_id: str) -> list[Blocker]: ...

    async def save_status_update(self, status_update: StatusUpdate) -> StatusUpdate: ...
    async def list_status_updates_for_project(self, project_id: str) -> list[StatusUpdate]: ...


class PostgresProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_project(self, project: Project) -> Project:
        row = await self._session.get(ProjectRow, project.project_id)
        if row is None:
            row = ProjectRow(project_id=project.project_id, created_at=project.created_at)
            self._session.add(row)
        row.user_id = project.user_id
        row.name = project.name
        row.description = project.description
        row.status = project.status.value
        row.document_links = project.document_links
        row.updated_at = project.updated_at
        await self._session.flush()
        return project

    async def get_project(self, project_id: str) -> Project | None:
        row = await self._session.get(ProjectRow, project_id)
        return _row_to_project(row) if row is not None else None

    async def list_projects_for_user(self, user_id: str) -> list[Project]:
        result = await self._session.execute(
            select(ProjectRow).where(ProjectRow.user_id == user_id)
        )
        return [_row_to_project(row) for row in result.scalars().all()]

    async def save_goal(self, goal: Goal) -> Goal:
        row = await self._session.get(GoalRow, goal.goal_id)
        if row is None:
            row = GoalRow(
                goal_id=goal.goal_id, project_id=goal.project_id, created_at=goal.created_at
            )
            self._session.add(row)
        row.description = goal.description
        row.status = goal.status.value
        row.updated_at = goal.updated_at
        await self._session.flush()
        return goal

    async def list_goals_for_project(self, project_id: str) -> list[Goal]:
        result = await self._session.execute(
            select(GoalRow).where(GoalRow.project_id == project_id)
        )
        return [_row_to_goal(row) for row in result.scalars().all()]

    async def save_milestone(self, milestone: Milestone) -> Milestone:
        row = await self._session.get(MilestoneRow, milestone.milestone_id)
        if row is None:
            row = MilestoneRow(
                milestone_id=milestone.milestone_id,
                project_id=milestone.project_id,
                created_at=milestone.created_at,
            )
            self._session.add(row)
        row.name = milestone.name
        row.due_date = milestone.due_date
        row.status = milestone.status.value
        row.completed_at = milestone.completed_at
        await self._session.flush()
        return milestone

    async def get_milestone(self, milestone_id: str) -> Milestone | None:
        row = await self._session.get(MilestoneRow, milestone_id)
        return _row_to_milestone(row) if row is not None else None

    async def list_milestones_for_project(self, project_id: str) -> list[Milestone]:
        result = await self._session.execute(
            select(MilestoneRow).where(MilestoneRow.project_id == project_id)
        )
        return [_row_to_milestone(row) for row in result.scalars().all()]

    async def save_task(self, task: Task) -> Task:
        row = await self._session.get(TaskRow, task.task_id)
        if row is None:
            row = TaskRow(
                task_id=task.task_id, project_id=task.project_id, created_at=task.created_at
            )
            self._session.add(row)
        row.milestone_id = task.milestone_id
        row.description = task.description
        row.status = task.status.value
        row.updated_at = task.updated_at
        await self._session.flush()
        return task

    async def get_task(self, task_id: str) -> Task | None:
        row = await self._session.get(TaskRow, task_id)
        return _row_to_task(row) if row is not None else None

    async def list_tasks_for_project(self, project_id: str) -> list[Task]:
        result = await self._session.execute(
            select(TaskRow).where(TaskRow.project_id == project_id)
        )
        return [_row_to_task(row) for row in result.scalars().all()]

    async def save_decision(self, decision: Decision) -> Decision:
        # Immutable/append-only — always an insert, never an update
        # (Docs/DATA_MODEL.md), matching PortfolioSnapshot's precedent.
        self._session.add(
            DecisionRow(
                decision_id=decision.decision_id,
                project_id=decision.project_id,
                description=decision.description,
                rationale=decision.rationale,
                decided_at=decision.decided_at,
                source_context=decision.source_context,
            )
        )
        await self._session.flush()
        return decision

    async def list_decisions_for_project(self, project_id: str) -> list[Decision]:
        result = await self._session.execute(
            select(DecisionRow).where(DecisionRow.project_id == project_id)
        )
        return [_row_to_decision(row) for row in result.scalars().all()]

    async def save_blocker(self, blocker: Blocker) -> Blocker:
        row = await self._session.get(BlockerRow, blocker.blocker_id)
        if row is None:
            row = BlockerRow(
                blocker_id=blocker.blocker_id,
                project_id=blocker.project_id,
                created_at=blocker.created_at,
            )
            self._session.add(row)
        row.description = blocker.description
        row.status = blocker.status.value
        row.resolved_at = blocker.resolved_at
        await self._session.flush()
        return blocker

    async def get_blocker(self, blocker_id: str) -> Blocker | None:
        row = await self._session.get(BlockerRow, blocker_id)
        return _row_to_blocker(row) if row is not None else None

    async def list_blockers_for_project(self, project_id: str) -> list[Blocker]:
        result = await self._session.execute(
            select(BlockerRow).where(BlockerRow.project_id == project_id)
        )
        return [_row_to_blocker(row) for row in result.scalars().all()]

    async def save_status_update(self, status_update: StatusUpdate) -> StatusUpdate:
        # Immutable/append-only, same discipline as save_decision.
        self._session.add(
            StatusUpdateRow(
                status_update_id=status_update.status_update_id,
                project_id=status_update.project_id,
                summary=status_update.summary,
                created_at=status_update.created_at,
            )
        )
        await self._session.flush()
        return status_update

    async def list_status_updates_for_project(self, project_id: str) -> list[StatusUpdate]:
        result = await self._session.execute(
            select(StatusUpdateRow).where(StatusUpdateRow.project_id == project_id)
        )
        return [_row_to_status_update(row) for row in result.scalars().all()]
