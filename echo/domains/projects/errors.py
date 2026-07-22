from core.errors import EchoError, Severity


class ProjectNotFoundError(EchoError):
    code = "project_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class GoalNotFoundError(EchoError):
    code = "goal_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class MilestoneNotFoundError(EchoError):
    code = "milestone_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class TaskNotFoundError(EchoError):
    code = "task_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class BlockerNotFoundError(EchoError):
    code = "blocker_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class InvalidTaskTransitionError(EchoError):
    """PROMPT.md Phase 23 verification 3: a task cannot skip straight from
    `PROPOSED` to `IN_PROGRESS`/`DONE` — it must be explicitly `COMMITTED`
    first, mirroring domains/approvals/errors.py's own
    `InvalidStateTransitionError`."""

    code = "invalid_task_transition"
    retryable = False
    severity = Severity.MEDIUM
    http_status = 409
