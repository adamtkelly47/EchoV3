"""Projects' own data contracts (Docs/DOMAIN_OWNERSHIP.md: "Projects owns
persistent initiatives requiring multiple coordinated actions over time
... Projects organize work. Projects do not execute work."). `Decision` and
`StatusUpdate` are immutable, append-only records — the same pattern as
`PortfolioSnapshot`/`NewsDigest`: a correction is a new row, never an edit,
which is what makes PROMPT.md Phase 23 verification 2 ("decisions are
historically traceable") true structurally rather than by convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.projects.models import (
    BlockerStatus,
    GoalStatus,
    MilestoneStatus,
    ProjectStatus,
    TaskStatus,
)


class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: new_id("project"))
    user_id: str
    name: str
    description: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    document_links: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class Goal(BaseModel):
    goal_id: str = Field(default_factory=lambda: new_id("goal"))
    project_id: str
    description: str
    status: GoalStatus = GoalStatus.OPEN
    created_at: datetime
    updated_at: datetime


class Milestone(BaseModel):
    milestone_id: str = Field(default_factory=lambda: new_id("milestone"))
    project_id: str
    name: str
    due_date: datetime | None = None
    status: MilestoneStatus = MilestoneStatus.PENDING
    completed_at: datetime | None = None
    created_at: datetime


class Task(BaseModel):
    """`status` defaults to `PROPOSED` — a task only ever starts as
    something the assistant suggested, never silently created as already
    `COMMITTED` (PROMPT.md Phase 23 verification 3)."""

    task_id: str = Field(default_factory=lambda: new_id("task"))
    project_id: str
    milestone_id: str | None = None
    description: str
    status: TaskStatus = TaskStatus.PROPOSED
    created_at: datetime
    updated_at: datetime


class Decision(BaseModel):
    """Immutable — recorded once, never edited (PROMPT.md Phase 23
    verification 2: "decisions are historically traceable"). `source_context`
    is typically the conversation session id the decision came out of, so a
    later reader can trace exactly where it originated."""

    decision_id: str = Field(default_factory=lambda: new_id("decision"))
    project_id: str
    description: str
    rationale: str | None = None
    decided_at: datetime
    source_context: str | None = None


class Blocker(BaseModel):
    blocker_id: str = Field(default_factory=lambda: new_id("blocker"))
    project_id: str
    description: str
    status: BlockerStatus = BlockerStatus.OPEN
    created_at: datetime
    resolved_at: datetime | None = None


class StatusUpdate(BaseModel):
    """Immutable — a new row per update, matching `Decision`'s own
    append-only discipline."""

    status_update_id: str = Field(default_factory=lambda: new_id("statusupdate"))
    project_id: str
    summary: str
    created_at: datetime


class ProjectStatusSummary(BaseModel):
    """PROMPT.md Phase 23 implement item 1 / verification 1: "project
    status is based on stored facts." Every field here is a real count or a
    real record already on file — never a free-text status an assistant
    could invent. Computed fresh on every read (`domains/projects/policies.
    py`'s `compute_project_status_summary`), the same computed-not-stored
    pattern as `MoneyDashboard`/`InsiderProfile`."""

    project_id: str
    project_status: ProjectStatus
    total_tasks: int
    proposed_tasks: int
    committed_tasks: int
    in_progress_tasks: int
    done_tasks: int
    open_blockers: int
    next_milestone: Milestone | None
    overdue_milestones: list[Milestone]
    latest_status_update: StatusUpdate | None
    latest_decision: Decision | None
    generated_at: datetime
