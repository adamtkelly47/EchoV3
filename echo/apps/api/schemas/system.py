"""API-boundary request/response schemas — never the domain's own
MonitorDefinition/Alert crossing the wire directly (CONSTITUTION.md: Typed
Contracts), matching every other apps/api/schemas/*.py convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateMonitorRequest(BaseModel):
    user_id: str
    monitor_type: str
    quiet_hours_start_utc: int | None = None
    quiet_hours_end_utc: int | None = None


class SetMonitorEnabledRequest(BaseModel):
    enabled: bool


class MonitorResponse(BaseModel):
    monitor_id: str
    user_id: str
    monitor_type: str
    enabled: bool
    quiet_hours_start_utc: int | None
    quiet_hours_end_utc: int | None
    created_at: datetime
    updated_at: datetime


class AlertResponse(BaseModel):
    alert_id: str
    monitor_id: str
    user_id: str
    monitor_type: str
    severity: str
    message: str
    reason: str
    status: str
    triggered_at: datetime
    created_during_quiet_hours: bool
    acknowledged_at: datetime | None


class EvaluationRunResponse(BaseModel):
    evaluation_id: str
    monitor_id: str
    user_id: str
    monitor_type: str
    evaluated_at: datetime
    triggered: bool
    detail: str | None
