"""Projects' aggregate-lifecycle owner (Docs/DOMAIN_OWNERSHIP.md: "Projects
owns: project lifecycle, goal tracking, milestone management, dependency
management, progress evaluation, project completion, project archival").
No external providers (DOMAIN_OWNERSHIP.md: "External Providers: None —
third-party project management systems are providers rather than owners")
— everything here is pure domain state, no provider ports at all, unlike
every other domain this codebase has built so far.
"""

from __future__ import annotations

from datetime import datetime

from core.time import Clock
from domains.projects.errors import (
    BlockerNotFoundError,
    GoalNotFoundError,
    InvalidTaskTransitionError,
    MilestoneNotFoundError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from domains.projects.models import (
    TASK_VALID_TRANSITIONS,
    BlockerStatus,
    GoalStatus,
    MilestoneStatus,
    ProjectStatus,
    TaskStatus,
)
from domains.projects.policies import compute_project_status_summary
from domains.projects.repository import ProjectRepository
from domains.projects.schemas import (
    Blocker,
    Decision,
    Goal,
    Milestone,
    Project,
    ProjectStatusSummary,
    StatusUpdate,
    Task,
)
from infrastructure.database.repositories.audit import AuditRepository


class ProjectService:
    def __init__(self, repository: ProjectRepository, audit: AuditRepository, clock: Clock) -> None:
        self._repository = repository
        self._audit = audit
        self._clock = clock

    async def create_project(
        self, user_id: str, name: str, description: str | None = None
    ) -> Project:
        now = self._clock.now_utc()
        project = Project(
            user_id=user_id, name=name, description=description, created_at=now, updated_at=now
        )
        await self._repository.save_project(project)
        await self._audit.record(
            action="projects.project_created",
            result="success",
            detail={"project_id": project.project_id, "name": name},
        )
        return project

    async def get_project(self, project_id: str) -> Project:
        return await self._require_project(project_id)

    async def list_projects_for_user(self, user_id: str) -> list[Project]:
        return await self._repository.list_projects_for_user(user_id)

    async def update_project_status(self, project_id: str, status: ProjectStatus) -> Project:
        project = await self._require_project(project_id)
        updated = project.model_copy(update={"status": status, "updated_at": self._clock.now_utc()})
        await self._repository.save_project(updated)
        return updated

    async def add_document_link(self, project_id: str, url: str) -> Project:
        """PROMPT.md Phase 23 implement item 8: "relevant document links."
        A plain reference (a URL) — Projects stores the link, it never
        fetches or interprets the document itself."""
        project = await self._require_project(project_id)
        updated = project.model_copy(
            update={
                "document_links": [*project.document_links, url],
                "updated_at": self._clock.now_utc(),
            }
        )
        await self._repository.save_project(updated)
        return updated

    async def add_goal(self, project_id: str, description: str) -> Goal:
        await self._require_project(project_id)
        now = self._clock.now_utc()
        goal = Goal(project_id=project_id, description=description, created_at=now, updated_at=now)
        await self._repository.save_goal(goal)
        return goal

    async def list_goals_for_project(self, project_id: str) -> list[Goal]:
        return await self._repository.list_goals_for_project(project_id)

    async def update_goal_status(self, goal_id: str, status: GoalStatus, project_id: str) -> Goal:
        goals = await self._repository.list_goals_for_project(project_id)
        goal = next((g for g in goals if g.goal_id == goal_id), None)
        if goal is None:
            raise GoalNotFoundError(f"no goal {goal_id!r} for project {project_id!r}")
        updated = goal.model_copy(update={"status": status, "updated_at": self._clock.now_utc()})
        await self._repository.save_goal(updated)
        return updated

    async def add_milestone(
        self, project_id: str, name: str, due_date: datetime | None = None
    ) -> Milestone:
        await self._require_project(project_id)
        milestone = Milestone(
            project_id=project_id, name=name, due_date=due_date, created_at=self._clock.now_utc()
        )
        await self._repository.save_milestone(milestone)
        return milestone

    async def list_milestones_for_project(self, project_id: str) -> list[Milestone]:
        return await self._repository.list_milestones_for_project(project_id)

    async def complete_milestone(self, milestone_id: str) -> Milestone:
        milestone = await self._repository.get_milestone(milestone_id)
        if milestone is None:
            raise MilestoneNotFoundError(f"no milestone found with id {milestone_id!r}")
        updated = milestone.model_copy(
            update={"status": MilestoneStatus.COMPLETED, "completed_at": self._clock.now_utc()}
        )
        await self._repository.save_milestone(updated)
        await self._audit.record(
            action="projects.milestone_completed",
            result="success",
            detail={"milestone_id": milestone_id, "project_id": milestone.project_id},
        )
        return updated

    async def propose_task(
        self, project_id: str, description: str, milestone_id: str | None = None
    ) -> Task:
        """PROMPT.md Phase 23 verification 3: every task starts life as
        `PROPOSED` — the assistant may suggest a task during a
        conversation, but that alone never makes it real work the user is
        committed to."""
        await self._require_project(project_id)
        now = self._clock.now_utc()
        task = Task(
            project_id=project_id,
            milestone_id=milestone_id,
            description=description,
            created_at=now,
            updated_at=now,
        )
        await self._repository.save_task(task)
        return task

    async def list_tasks_for_project(self, project_id: str) -> list[Task]:
        return await self._repository.list_tasks_for_project(project_id)

    async def commit_task(self, task_id: str) -> Task:
        """PROMPT.md Phase 23 verification 3: the user explicitly agreeing
        to do this task — the one transition that turns a suggestion into
        committed work. Audited, unlike other task transitions, since it's
        the moment a task becomes real."""
        task = await self._transition_task(task_id, TaskStatus.COMMITTED)
        await self._audit.record(
            action="projects.task_committed",
            result="success",
            detail={"task_id": task_id, "project_id": task.project_id},
        )
        return task

    async def start_task(self, task_id: str) -> Task:
        return await self._transition_task(task_id, TaskStatus.IN_PROGRESS)

    async def complete_task(self, task_id: str) -> Task:
        return await self._transition_task(task_id, TaskStatus.DONE)

    async def cancel_task(self, task_id: str) -> Task:
        return await self._transition_task(task_id, TaskStatus.CANCELLED)

    async def _transition_task(self, task_id: str, target: TaskStatus) -> Task:
        task = await self._repository.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(f"no task found with id {task_id!r}")
        if target not in TASK_VALID_TRANSITIONS[task.status]:
            raise InvalidTaskTransitionError(
                f"task {task_id!r} cannot move from {task.status.value} to {target.value}"
            )
        updated = task.model_copy(update={"status": target, "updated_at": self._clock.now_utc()})
        await self._repository.save_task(updated)
        return updated

    async def record_decision(
        self,
        project_id: str,
        description: str,
        rationale: str | None = None,
        source_context: str | None = None,
    ) -> Decision:
        """PROMPT.md Phase 23 verification 2: "decisions are historically
        traceable" — an immutable, append-only record; there is no
        `update_decision`, only new ones."""
        await self._require_project(project_id)
        decision = Decision(
            project_id=project_id,
            description=description,
            rationale=rationale,
            decided_at=self._clock.now_utc(),
            source_context=source_context,
        )
        await self._repository.save_decision(decision)
        await self._audit.record(
            action="projects.decision_recorded",
            result="success",
            detail={"decision_id": decision.decision_id, "project_id": project_id},
        )
        return decision

    async def list_decisions_for_project(self, project_id: str) -> list[Decision]:
        return await self._repository.list_decisions_for_project(project_id)

    async def raise_blocker(self, project_id: str, description: str) -> Blocker:
        await self._require_project(project_id)
        blocker = Blocker(
            project_id=project_id, description=description, created_at=self._clock.now_utc()
        )
        await self._repository.save_blocker(blocker)
        await self._audit.record(
            action="projects.blocker_raised",
            result="success",
            detail={"blocker_id": blocker.blocker_id, "project_id": project_id},
        )
        return blocker

    async def resolve_blocker(self, blocker_id: str) -> Blocker:
        blocker = await self._repository.get_blocker(blocker_id)
        if blocker is None:
            raise BlockerNotFoundError(f"no blocker found with id {blocker_id!r}")
        updated = blocker.model_copy(
            update={"status": BlockerStatus.RESOLVED, "resolved_at": self._clock.now_utc()}
        )
        await self._repository.save_blocker(updated)
        await self._audit.record(
            action="projects.blocker_resolved",
            result="success",
            detail={"blocker_id": blocker_id, "project_id": blocker.project_id},
        )
        return updated

    async def list_blockers_for_project(self, project_id: str) -> list[Blocker]:
        return await self._repository.list_blockers_for_project(project_id)

    async def record_status_update(self, project_id: str, summary: str) -> StatusUpdate:
        await self._require_project(project_id)
        status_update = StatusUpdate(
            project_id=project_id, summary=summary, created_at=self._clock.now_utc()
        )
        await self._repository.save_status_update(status_update)
        return status_update

    async def list_status_updates_for_project(self, project_id: str) -> list[StatusUpdate]:
        return await self._repository.list_status_updates_for_project(project_id)

    async def get_project_status_summary(self, project_id: str) -> ProjectStatusSummary:
        """PROMPT.md Phase 23 implement item 1 / verification 1: computed
        fresh from stored facts on every read — never persisted, the same
        computed-not-stored pattern as `PortfolioService.get_dashboard`."""
        project = await self._require_project(project_id)
        tasks = await self._repository.list_tasks_for_project(project_id)
        milestones = await self._repository.list_milestones_for_project(project_id)
        blockers = await self._repository.list_blockers_for_project(project_id)
        status_updates = await self._repository.list_status_updates_for_project(project_id)
        decisions = await self._repository.list_decisions_for_project(project_id)
        return compute_project_status_summary(
            project,
            tasks,
            milestones,
            blockers,
            status_updates,
            decisions,
            self._clock.now_utc(),
        )

    async def _require_project(self, project_id: str) -> Project:
        project = await self._repository.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(f"no project found with id {project_id!r}")
        return project
