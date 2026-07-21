"""Deterministic escalation policy (Docs/MODEL_ROUTING.md, ADR_0004): whether
a task escalates from Ollama to Claude is decided by this function, never by
prompt wording or model self-selection (CONSTITUTION.md: Prompt Philosophy;
Capability Planner — "Language models SHALL NOT... execute capabilities
directly" applies equally to models choosing their own provider).
"""

from __future__ import annotations

from providers.models.contracts import TaskType

DEFAULT_CONFIDENCE_THRESHOLD = 0.6


def should_escalate(
    task_type: TaskType,
    *,
    schema_validation_failed: bool = False,
    local_confidence: float | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    is_consequential: bool = False,
) -> bool:
    """Per Docs/MODEL_ROUTING.md's escalation criteria: direct user
    conversation always escalates; a failed local schema validation
    escalates; low local-model confidence escalates; a consequential
    recommendation escalates. Anything else stays local."""
    if task_type == TaskType.CONVERSATION:
        return True
    if schema_validation_failed:
        return True
    if local_confidence is not None and local_confidence < confidence_threshold:
        return True
    return bool(is_consequential)
