from __future__ import annotations

from typing import Any

from domains.projects.schemas import Blocker, Decision, Goal, Milestone, Project, StatusUpdate, Task


class FakeProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.goals: dict[str, Goal] = {}
        self.milestones: dict[str, Milestone] = {}
        self.tasks: dict[str, Task] = {}
        self.decisions: list[Decision] = []
        self.blockers: dict[str, Blocker] = {}
        self.status_updates: list[StatusUpdate] = []

    async def save_project(self, project: Project) -> Project:
        self.projects[project.project_id] = project
        return project

    async def get_project(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    async def list_projects_for_user(self, user_id: str) -> list[Project]:
        return [p for p in self.projects.values() if p.user_id == user_id]

    async def save_goal(self, goal: Goal) -> Goal:
        self.goals[goal.goal_id] = goal
        return goal

    async def list_goals_for_project(self, project_id: str) -> list[Goal]:
        return [g for g in self.goals.values() if g.project_id == project_id]

    async def save_milestone(self, milestone: Milestone) -> Milestone:
        self.milestones[milestone.milestone_id] = milestone
        return milestone

    async def get_milestone(self, milestone_id: str) -> Milestone | None:
        return self.milestones.get(milestone_id)

    async def list_milestones_for_project(self, project_id: str) -> list[Milestone]:
        return [m for m in self.milestones.values() if m.project_id == project_id]

    async def save_task(self, task: Task) -> Task:
        self.tasks[task.task_id] = task
        return task

    async def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    async def list_tasks_for_project(self, project_id: str) -> list[Task]:
        return [t for t in self.tasks.values() if t.project_id == project_id]

    async def save_decision(self, decision: Decision) -> Decision:
        self.decisions.append(decision)
        return decision

    async def list_decisions_for_project(self, project_id: str) -> list[Decision]:
        return [d for d in self.decisions if d.project_id == project_id]

    async def save_blocker(self, blocker: Blocker) -> Blocker:
        self.blockers[blocker.blocker_id] = blocker
        return blocker

    async def get_blocker(self, blocker_id: str) -> Blocker | None:
        return self.blockers.get(blocker_id)

    async def list_blockers_for_project(self, project_id: str) -> list[Blocker]:
        return [b for b in self.blockers.values() if b.project_id == project_id]

    async def save_status_update(self, status_update: StatusUpdate) -> StatusUpdate:
        self.status_updates.append(status_update)
        return status_update

    async def list_status_updates_for_project(self, project_id: str) -> list[StatusUpdate]:
        return [s for s in self.status_updates if s.project_id == project_id]


class FakeAuditRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        call_id = f"audit_fake_{len(self.recorded)}"
        self.recorded.append(
            {"audit_id": call_id, "action": action, "result": result, "detail": detail}
        )
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e.get("correlation_id") == correlation_id]
