"""API-boundary request/response schemas — never the domain's own
Project/Task/... crossing the wire directly (CONSTITUTION.md: Typed
Contracts), matching every other apps/api/schemas/*.py convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    user_id: str
    name: str
    description: str | None = None


class UpdateProjectStatusRequest(BaseModel):
    status: str


class AddDocumentLinkRequest(BaseModel):
    url: str


class ProjectResponse(BaseModel):
    project_id: str
    user_id: str
    name: str
    description: str | None
    status: str
    document_links: list[str]
    created_at: datetime
    updated_at: datetime


class CreateGoalRequest(BaseModel):
    description: str


class UpdateGoalStatusRequest(BaseModel):
    status: str


class GoalResponse(BaseModel):
    goal_id: str
    project_id: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


class CreateMilestoneRequest(BaseModel):
    name: str
    due_date: datetime | None = None


class MilestoneResponse(BaseModel):
    milestone_id: str
    project_id: str
    name: str
    due_date: datetime | None
    status: str
    completed_at: datetime | None
    created_at: datetime


class ProposeTaskRequest(BaseModel):
    description: str
    milestone_id: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    project_id: str
    milestone_id: str | None
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


class RecordDecisionRequest(BaseModel):
    description: str
    rationale: str | None = None
    source_context: str | None = None


class DecisionResponse(BaseModel):
    decision_id: str
    project_id: str
    description: str
    rationale: str | None
    decided_at: datetime
    source_context: str | None
    memory_id: str | None = None


class RaiseBlockerRequest(BaseModel):
    description: str


class BlockerResponse(BaseModel):
    blocker_id: str
    project_id: str
    description: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


class RecordStatusUpdateRequest(BaseModel):
    summary: str


class StatusUpdateResponse(BaseModel):
    status_update_id: str
    project_id: str
    summary: str
    created_at: datetime


class ProjectStatusSummaryResponse(BaseModel):
    project_id: str
    project_status: str
    total_tasks: int
    proposed_tasks: int
    committed_tasks: int
    in_progress_tasks: int
    done_tasks: int
    open_blockers: int
    next_milestone: MilestoneResponse | None
    overdue_milestones: list[MilestoneResponse]
    latest_status_update: StatusUpdateResponse | None
    latest_decision: DecisionResponse | None
    generated_at: datetime
