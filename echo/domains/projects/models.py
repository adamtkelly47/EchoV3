"""PROMPT.md Phase 23: durable project state. `TASK_VALID_TRANSITIONS`
enforces PROMPT.md verification 3 ("the assistant distinguishes proposed
tasks from committed tasks") in code, not merely convention — a task
cannot become `IN_PROGRESS`/`DONE` without first passing through
`COMMITTED`, the same "invalid transitions are rejected in code" discipline
domains/approvals/models.py established for its own state machine.
"""

from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class GoalStatus(str, Enum):
    OPEN = "open"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class TaskStatus(str, Enum):
    """PROMPT.md Phase 23 verification 3: `PROPOSED` (the assistant
    suggested this task; the user has not yet agreed to it) and
    `COMMITTED` (the user has actually agreed to do it) are distinct, real
    states — never collapsed into a single generic "open" status."""

    PROPOSED = "proposed"
    COMMITTED = "committed"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


TASK_VALID_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PROPOSED: frozenset({TaskStatus.COMMITTED, TaskStatus.CANCELLED}),
    TaskStatus.COMMITTED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.DONE, TaskStatus.CANCELLED}),
    TaskStatus.DONE: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


class BlockerStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
