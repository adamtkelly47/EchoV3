"""System's own data contracts (Docs/DOMAIN_OWNERSHIP.md: System owns
"System Alerts", "Diagnostics", "platform monitoring"). `Alert` is an
immutable-except-status-transition record — the underlying facts
(`message`, `reason`, `dedup_key`, `triggered_at`) never change after
creation, matching every other domain's "a correction is a new record"
discipline; only `status`/`acknowledged_at` move forward through
`domains/system/service.py`'s own transition methods.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.system.models import (
    AlertSeverity,
    AlertStatus,
    HallucinationIncidentStatus,
    MonitorType,
)


class MonitorDefinition(BaseModel):
    """PROMPT.md Phase 24 implement items 1-2: "monitor definitions" and
    "trigger schedules." `quiet_hours_start_utc`/`quiet_hours_end_utc` are
    plain UTC hour-of-day integers (0-23) — no Identity/timezone-preference
    domain exists yet to resolve a real local time, a documented, honest
    scope limitation rather than a fabricated timezone conversion."""

    monitor_id: str = Field(default_factory=lambda: new_id("monitor"))
    user_id: str
    monitor_type: MonitorType
    enabled: bool = True
    quiet_hours_start_utc: int | None = None
    quiet_hours_end_utc: int | None = None
    created_at: datetime
    updated_at: datetime


class Alert(BaseModel):
    """`reason` exists specifically to satisfy PROMPT.md Phase 24
    verification 3 ("every alert shows why it triggered") — an alert with
    no stated reason is not allowed to exist in this schema, the same
    discipline `domains/research/schemas.py`'s `AnomalyFeature.
    baseline_description` established for anomaly claims."""

    alert_id: str = Field(default_factory=lambda: new_id("alert"))
    monitor_id: str
    user_id: str
    monitor_type: MonitorType
    severity: AlertSeverity
    message: str
    reason: str
    dedup_key: str
    status: AlertStatus = AlertStatus.ACTIVE
    triggered_at: datetime
    created_during_quiet_hours: bool = False
    acknowledged_at: datetime | None = None


class EvaluationRun(BaseModel):
    """PROMPT.md Phase 24 implement item 10: "evaluation audit." One row
    per monitor per sweep, regardless of whether it triggered — an
    inspectable record that the condition was actually checked, not just a
    log line that disappears when nothing happens."""

    evaluation_id: str = Field(default_factory=lambda: new_id("evalrun"))
    monitor_id: str
    user_id: str
    monitor_type: MonitorType
    evaluated_at: datetime
    triggered: bool
    detail: str | None = None


class HallucinationIncident(BaseModel):
    """PROMPT.md Phase 25 tracked item 7. A human-reported claim: no
    automatic hallucination detector exists (or is claimed) anywhere in
    this codebase — every incident starts from a person noticing Echo
    said something unsupported or false, matching CONSTITUTION.md's own
    stance that only a human, not the model itself, can judge this."""

    incident_id: str = Field(default_factory=lambda: new_id("hallucination"))
    user_id: str
    correlation_id: str | None = None
    description: str
    status: HallucinationIncidentStatus = HallucinationIncidentStatus.OPEN
    reported_at: datetime
    resolution_note: str | None = None
    resolved_at: datetime | None = None


class RegressionCase(BaseModel):
    """PROMPT.md Phase 25: "Create regression datasets from corrected
    failures." Built automatically from a resolved `HallucinationIncident`
    or a user-initiated memory correction (`application/orchestrators/
    trust.py`) — capturing what Echo actually got wrong and what the
    correct answer was, so a future evaluation pass has real, non-synthetic
    cases to check against rather than starting from nothing."""

    case_id: str = Field(default_factory=lambda: new_id("regression"))
    source_type: str
    source_id: str
    incorrect_output: str
    corrected_output: str
    created_at: datetime
