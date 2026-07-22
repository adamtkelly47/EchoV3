"""System's aggregate-lifecycle owner for monitors/alerts (Docs/
DOMAIN_OWNERSHIP.md: System owns "platform monitoring", "system alert
generation", "raise alert"/"acknowledge alert"). No provider ports here —
System never talks to an external system directly; every real condition it
evaluates comes from another domain's own already-synced state, read by
`application/orchestrators/monitoring.py` (the Application layer, since
CONSTITUTION.md reserves cross-domain coordination for it).
"""

from __future__ import annotations

from datetime import datetime

from core.time import Clock
from domains.system.errors import (
    AlertNotFoundError,
    HallucinationIncidentAlreadyResolvedError,
    HallucinationIncidentNotFoundError,
    InvalidAlertTransitionError,
    MonitorNotFoundError,
)
from domains.system.models import (
    AlertSeverity,
    AlertStatus,
    HallucinationIncidentStatus,
    MonitorType,
)
from domains.system.repository import SystemRepository
from domains.system.schemas import (
    Alert,
    EvaluationRun,
    HallucinationIncident,
    MonitorDefinition,
    RegressionCase,
)
from infrastructure.database.repositories.audit import AuditRepository


class SystemService:
    def __init__(self, repository: SystemRepository, audit: AuditRepository, clock: Clock) -> None:
        self._repository = repository
        self._audit = audit
        self._clock = clock

    async def create_monitor(
        self,
        user_id: str,
        monitor_type: MonitorType,
        *,
        quiet_hours_start_utc: int | None = None,
        quiet_hours_end_utc: int | None = None,
    ) -> MonitorDefinition:
        now = self._clock.now_utc()
        monitor = MonitorDefinition(
            user_id=user_id,
            monitor_type=monitor_type,
            quiet_hours_start_utc=quiet_hours_start_utc,
            quiet_hours_end_utc=quiet_hours_end_utc,
            created_at=now,
            updated_at=now,
        )
        await self._repository.save_monitor(monitor)
        await self._audit.record(
            action="system.monitor_created",
            result="success",
            detail={"monitor_id": monitor.monitor_id, "monitor_type": monitor_type.value},
        )
        return monitor

    async def get_monitor(self, monitor_id: str) -> MonitorDefinition:
        return await self._require_monitor(monitor_id)

    async def list_monitors_for_user(self, user_id: str) -> list[MonitorDefinition]:
        return await self._repository.list_monitors_for_user(user_id)

    async def list_all_enabled_monitors(self) -> list[MonitorDefinition]:
        return await self._repository.list_all_enabled_monitors()

    async def set_monitor_enabled(self, monitor_id: str, enabled: bool) -> MonitorDefinition:
        """PROMPT.md Phase 24 verification 4: "users can disable a
        monitor.\" """
        monitor = await self._require_monitor(monitor_id)
        updated = monitor.model_copy(
            update={"enabled": enabled, "updated_at": self._clock.now_utc()}
        )
        await self._repository.save_monitor(updated)
        await self._audit.record(
            action="system.monitor_enabled_changed",
            result="success",
            detail={"monitor_id": monitor_id, "enabled": enabled},
        )
        return updated

    async def raise_alert(
        self,
        monitor: MonitorDefinition,
        *,
        message: str,
        reason: str,
        severity: str,
        dedup_key: str,
        created_during_quiet_hours: bool,
    ) -> Alert | None:
        """PROMPT.md Phase 24 verification 2: "duplicate alerts are
        suppressed" — enforced here, not left to the caller, so no
        evaluator can accidentally skip the dedup check. Returns `None`
        (not an error) when an active alert with this exact `dedup_key`
        already exists — deduplication is an expected, routine outcome of
        a monitor sweep, not a failure."""
        existing = await self._repository.get_active_alert_by_dedup_key(dedup_key)
        if existing is not None:
            return None
        alert = Alert(
            monitor_id=monitor.monitor_id,
            user_id=monitor.user_id,
            monitor_type=monitor.monitor_type,
            severity=AlertSeverity(severity),
            message=message,
            reason=reason,
            dedup_key=dedup_key,
            triggered_at=self._clock.now_utc(),
            created_during_quiet_hours=created_during_quiet_hours,
        )
        await self._repository.save_alert(alert)
        await self._audit.record(
            action="system.alert_raised",
            result="success",
            detail={
                "alert_id": alert.alert_id,
                "monitor_type": monitor.monitor_type.value,
                "dedup_key": dedup_key,
            },
        )
        return alert

    async def acknowledge_alert(self, alert_id: str) -> Alert:
        return await self._transition_alert(alert_id, AlertStatus.ACKNOWLEDGED)

    async def suppress_alert(self, alert_id: str) -> Alert:
        return await self._transition_alert(alert_id, AlertStatus.SUPPRESSED)

    async def _transition_alert(self, alert_id: str, target: AlertStatus) -> Alert:
        alert = await self._repository.get_alert(alert_id)
        if alert is None:
            raise AlertNotFoundError(f"no alert found with id {alert_id!r}")
        if alert.status != AlertStatus.ACTIVE:
            raise InvalidAlertTransitionError(
                f"alert {alert_id!r} is already {alert.status.value}, cannot move to {target.value}"
            )
        now = self._clock.now_utc()
        updated = alert.model_copy(
            update={
                "status": target,
                "acknowledged_at": now if target == AlertStatus.ACKNOWLEDGED else None,
            }
        )
        await self._repository.save_alert(updated)
        await self._audit.record(
            action=f"system.alert_{target.value}",
            result="success",
            detail={"alert_id": alert_id},
        )
        return updated

    async def list_alerts_for_user(self, user_id: str) -> list[Alert]:
        return await self._repository.list_alerts_for_user(user_id)

    async def record_evaluation_run(
        self, monitor: MonitorDefinition, *, triggered: bool, detail: str | None = None
    ) -> EvaluationRun:
        """PROMPT.md Phase 24 implement item 10: "evaluation audit" — one
        row per monitor per sweep, regardless of outcome."""
        run = EvaluationRun(
            monitor_id=monitor.monitor_id,
            user_id=monitor.user_id,
            monitor_type=monitor.monitor_type,
            evaluated_at=self._clock.now_utc(),
            triggered=triggered,
            detail=detail,
        )
        return await self._repository.save_evaluation_run(run)

    async def list_evaluation_runs_for_monitor(self, monitor_id: str) -> list[EvaluationRun]:
        return await self._repository.list_evaluation_runs_for_monitor(monitor_id)

    async def _require_monitor(self, monitor_id: str) -> MonitorDefinition:
        monitor = await self._repository.get_monitor(monitor_id)
        if monitor is None:
            raise MonitorNotFoundError(f"no monitor found with id {monitor_id!r}")
        return monitor

    async def report_hallucination(
        self, user_id: str, *, description: str, correlation_id: str | None = None
    ) -> HallucinationIncident:
        """PROMPT.md Phase 25 tracked item 7. No automatic detector decides
        this — a human noticing and reporting it is the only trigger, by
        design (CONSTITUTION.md: only a human can judge whether a claim
        was actually false or unsupported)."""
        incident = HallucinationIncident(
            user_id=user_id,
            correlation_id=correlation_id,
            description=description,
            reported_at=self._clock.now_utc(),
        )
        await self._repository.save_hallucination_incident(incident)
        await self._audit.record(
            action="system.hallucination_reported",
            result="success",
            correlation_id=correlation_id,
            detail={"incident_id": incident.incident_id},
        )
        return incident

    async def resolve_hallucination(
        self, incident_id: str, *, resolution_note: str
    ) -> HallucinationIncident:
        """Resolving also seeds a `RegressionCase` (PROMPT.md Phase 25:
        "Create regression datasets from corrected failures") — the
        incident's own description is the incorrect output being
        corrected, and `resolution_note` is what should have been said
        instead."""
        incident = await self._require_hallucination_incident(incident_id)
        if incident.status == HallucinationIncidentStatus.RESOLVED:
            raise HallucinationIncidentAlreadyResolvedError(
                f"hallucination incident {incident_id!r} is already resolved"
            )
        resolved = incident.model_copy(
            update={
                "status": HallucinationIncidentStatus.RESOLVED,
                "resolution_note": resolution_note,
                "resolved_at": self._clock.now_utc(),
            }
        )
        await self._repository.save_hallucination_incident(resolved)
        await self._repository.save_regression_case(
            RegressionCase(
                source_type="hallucination_incident",
                source_id=resolved.incident_id,
                incorrect_output=resolved.description,
                corrected_output=resolution_note,
                created_at=self._clock.now_utc(),
            )
        )
        await self._audit.record(
            action="system.hallucination_resolved",
            result="success",
            correlation_id=incident.correlation_id,
            detail={"incident_id": incident_id},
        )
        return resolved

    async def list_hallucination_incidents_for_user(
        self, user_id: str
    ) -> list[HallucinationIncident]:
        return await self._repository.list_hallucination_incidents_for_user(user_id)

    async def list_hallucination_incidents_since(
        self, since: datetime
    ) -> list[HallucinationIncident]:
        return await self._repository.list_hallucination_incidents_since(since)

    async def record_regression_case(
        self, *, source_type: str, source_id: str, incorrect_output: str, corrected_output: str
    ) -> RegressionCase:
        """The second, non-hallucination path into the regression dataset
        (PROMPT.md Phase 25) — a user-initiated memory correction
        (`application/orchestrators/trust.py`'s `TrustOrchestrator.
        record_user_correction`) is exactly as real a "corrected failure"
        as a resolved hallucination incident."""
        case = RegressionCase(
            source_type=source_type,
            source_id=source_id,
            incorrect_output=incorrect_output,
            corrected_output=corrected_output,
            created_at=self._clock.now_utc(),
        )
        return await self._repository.save_regression_case(case)

    async def list_regression_cases(self) -> list[RegressionCase]:
        return await self._repository.list_regression_cases()

    async def _require_hallucination_incident(self, incident_id: str) -> HallucinationIncident:
        incident = await self._repository.get_hallucination_incident(incident_id)
        if incident is None:
            raise HallucinationIncidentNotFoundError(
                f"no hallucination incident found with id {incident_id!r}"
            )
        return incident
