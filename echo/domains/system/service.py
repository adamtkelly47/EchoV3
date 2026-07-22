"""System's aggregate-lifecycle owner for monitors/alerts (Docs/
DOMAIN_OWNERSHIP.md: System owns "platform monitoring", "system alert
generation", "raise alert"/"acknowledge alert"). No provider ports here —
System never talks to an external system directly; every real condition it
evaluates comes from another domain's own already-synced state, read by
`application/orchestrators/monitoring.py` (the Application layer, since
CONSTITUTION.md reserves cross-domain coordination for it).
"""

from __future__ import annotations

from core.time import Clock
from domains.system.errors import (
    AlertNotFoundError,
    InvalidAlertTransitionError,
    MonitorNotFoundError,
)
from domains.system.models import AlertSeverity, AlertStatus, MonitorType
from domains.system.repository import SystemRepository
from domains.system.schemas import Alert, EvaluationRun, MonitorDefinition
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
