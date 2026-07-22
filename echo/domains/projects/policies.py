"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as every other domain's own
policies.py.
"""

from __future__ import annotations

from datetime import datetime

from domains.projects.models import BlockerStatus, MilestoneStatus, TaskStatus
from domains.projects.schemas import (
    Blocker,
    Decision,
    Milestone,
    Project,
    ProjectStatusSummary,
    StatusUpdate,
    Task,
)


def is_milestone_overdue(milestone: Milestone, now: datetime) -> bool:
    if milestone.status == MilestoneStatus.COMPLETED or milestone.due_date is None:
        return False
    return milestone.due_date < now


def compute_project_status_summary(
    project: Project,
    tasks: list[Task],
    milestones: list[Milestone],
    blockers: list[Blocker],
    status_updates: list[StatusUpdate],
    decisions: list[Decision],
    now: datetime,
) -> ProjectStatusSummary:
    """PROMPT.md Phase 23 implement item 1 / verification 1: "project
    status is based on stored facts." Every number here is a count over
    real, already-persisted records — never an LLM-asserted summary."""
    pending_milestones = sorted(
        (m for m in milestones if m.status == MilestoneStatus.PENDING and m.due_date is not None),
        key=lambda m: m.due_date,  # type: ignore[arg-type, return-value]
    )
    overdue = [m for m in pending_milestones if is_milestone_overdue(m, now)]
    next_milestone = next((m for m in pending_milestones if not is_milestone_overdue(m, now)), None)

    latest_status_update = (
        max(status_updates, key=lambda s: s.created_at) if status_updates else None
    )
    latest_decision = max(decisions, key=lambda d: d.decided_at) if decisions else None

    return ProjectStatusSummary(
        project_id=project.project_id,
        project_status=project.status,
        total_tasks=len(tasks),
        proposed_tasks=sum(1 for t in tasks if t.status == TaskStatus.PROPOSED),
        committed_tasks=sum(1 for t in tasks if t.status == TaskStatus.COMMITTED),
        in_progress_tasks=sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS),
        done_tasks=sum(1 for t in tasks if t.status == TaskStatus.DONE),
        open_blockers=sum(1 for b in blockers if b.status == BlockerStatus.OPEN),
        next_milestone=next_milestone,
        overdue_milestones=overdue,
        latest_status_update=latest_status_update,
        latest_decision=latest_decision,
        generated_at=now,
    )
