from __future__ import annotations

from datetime import datetime
from typing import Any

from domains.system.models import AlertStatus
from domains.system.schemas import (
    Alert,
    EvaluationRun,
    HallucinationIncident,
    MonitorDefinition,
    RegressionCase,
)


class FakeSystemRepository:
    def __init__(self) -> None:
        self.monitors: dict[str, MonitorDefinition] = {}
        self.alerts: dict[str, Alert] = {}
        self.evaluation_runs: list[EvaluationRun] = []
        self.hallucination_incidents: dict[str, HallucinationIncident] = {}
        self.regression_cases: list[RegressionCase] = []

    async def save_monitor(self, monitor: MonitorDefinition) -> MonitorDefinition:
        self.monitors[monitor.monitor_id] = monitor
        return monitor

    async def get_monitor(self, monitor_id: str) -> MonitorDefinition | None:
        return self.monitors.get(monitor_id)

    async def list_monitors_for_user(self, user_id: str) -> list[MonitorDefinition]:
        return [m for m in self.monitors.values() if m.user_id == user_id]

    async def list_all_enabled_monitors(self) -> list[MonitorDefinition]:
        return [m for m in self.monitors.values() if m.enabled]

    async def save_alert(self, alert: Alert) -> Alert:
        self.alerts[alert.alert_id] = alert
        return alert

    async def get_alert(self, alert_id: str) -> Alert | None:
        return self.alerts.get(alert_id)

    async def list_alerts_for_user(self, user_id: str) -> list[Alert]:
        return [a for a in self.alerts.values() if a.user_id == user_id]

    async def get_active_alert_by_dedup_key(self, dedup_key: str) -> Alert | None:
        for alert in self.alerts.values():
            if alert.dedup_key == dedup_key and alert.status == AlertStatus.ACTIVE:
                return alert
        return None

    async def save_evaluation_run(self, run: EvaluationRun) -> EvaluationRun:
        self.evaluation_runs.append(run)
        return run

    async def list_evaluation_runs_for_monitor(self, monitor_id: str) -> list[EvaluationRun]:
        return [r for r in self.evaluation_runs if r.monitor_id == monitor_id]

    async def save_hallucination_incident(
        self, incident: HallucinationIncident
    ) -> HallucinationIncident:
        self.hallucination_incidents[incident.incident_id] = incident
        return incident

    async def get_hallucination_incident(self, incident_id: str) -> HallucinationIncident | None:
        return self.hallucination_incidents.get(incident_id)

    async def list_hallucination_incidents_for_user(
        self, user_id: str
    ) -> list[HallucinationIncident]:
        return [i for i in self.hallucination_incidents.values() if i.user_id == user_id]

    async def list_hallucination_incidents_since(
        self, since: datetime
    ) -> list[HallucinationIncident]:
        return [i for i in self.hallucination_incidents.values() if i.reported_at >= since]

    async def save_regression_case(self, case: RegressionCase) -> RegressionCase:
        self.regression_cases.append(case)
        return case

    async def list_regression_cases(self) -> list[RegressionCase]:
        return list(self.regression_cases)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []
        self.by_action: dict[str, list[dict[str, Any]]] = {}

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
        entry = {
            "audit_id": call_id,
            "action": action,
            "result": result,
            "correlation_id": correlation_id,
            "detail": detail,
        }
        self.recorded.append(entry)
        self.by_action.setdefault(action, []).append(entry)
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e.get("correlation_id") == correlation_id]

    async def list_recent_by_action(
        self, action: str, since: Any, *, result: str | None = None
    ) -> list[Any]:
        """Ignores `since` (no real timestamps on fake entries) — tests
        control what's "recent" by only adding entries meant to be seen."""
        entries = self.by_action.get(action, [])
        if result is not None:
            entries = [e for e in entries if e["result"] == result]
        return entries
