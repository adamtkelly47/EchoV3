"""System owns its own persistence (Docs/DOMAIN_OWNERSHIP.md: "System
repositories own: telemetry, metrics, diagnostics, runtime status,
operational logs, configuration metadata" — monitors/alerts are this
phase's own instance of "runtime status"/"diagnostics"), matching the
Approvals/Calendar/Portfolio/Research/Projects precedent of ORM tables
living inside the domain rather than infrastructure/database/tables/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import Boolean, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.system.models import AlertSeverity, AlertStatus, MonitorType
from domains.system.schemas import Alert, EvaluationRun, MonitorDefinition
from infrastructure.database.base import Base


class MonitorDefinitionRow(Base):
    __tablename__ = "system_monitor_definitions"

    monitor_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    monitor_type: Mapped[str] = mapped_column(String, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start_utc: Mapped[int | None] = mapped_column(Integer)
    quiet_hours_end_utc: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertRow(Base):
    __tablename__ = "system_alerts"

    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    monitor_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    monitor_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    dedup_key: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_during_quiet_hours: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationRunRow(Base):
    __tablename__ = "system_evaluation_runs"

    evaluation_id: Mapped[str] = mapped_column(String, primary_key=True)
    monitor_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    monitor_type: Mapped[str] = mapped_column(String)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    triggered: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str | None] = mapped_column(String)


def _row_to_monitor(row: MonitorDefinitionRow) -> MonitorDefinition:
    return MonitorDefinition(
        monitor_id=row.monitor_id,
        user_id=row.user_id,
        monitor_type=MonitorType(row.monitor_type),
        enabled=row.enabled,
        quiet_hours_start_utc=row.quiet_hours_start_utc,
        quiet_hours_end_utc=row.quiet_hours_end_utc,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_alert(row: AlertRow) -> Alert:
    return Alert(
        alert_id=row.alert_id,
        monitor_id=row.monitor_id,
        user_id=row.user_id,
        monitor_type=MonitorType(row.monitor_type),
        severity=AlertSeverity(row.severity),
        message=row.message,
        reason=row.reason,
        dedup_key=row.dedup_key,
        status=AlertStatus(row.status),
        triggered_at=row.triggered_at,
        created_during_quiet_hours=row.created_during_quiet_hours,
        acknowledged_at=row.acknowledged_at,
    )


def _row_to_evaluation_run(row: EvaluationRunRow) -> EvaluationRun:
    return EvaluationRun(
        evaluation_id=row.evaluation_id,
        monitor_id=row.monitor_id,
        user_id=row.user_id,
        monitor_type=MonitorType(row.monitor_type),
        evaluated_at=row.evaluated_at,
        triggered=row.triggered,
        detail=row.detail,
    )


class SystemRepository(Protocol):
    async def save_monitor(self, monitor: MonitorDefinition) -> MonitorDefinition: ...
    async def get_monitor(self, monitor_id: str) -> MonitorDefinition | None: ...
    async def list_monitors_for_user(self, user_id: str) -> list[MonitorDefinition]: ...
    async def list_all_enabled_monitors(self) -> list[MonitorDefinition]: ...

    async def save_alert(self, alert: Alert) -> Alert: ...
    async def get_alert(self, alert_id: str) -> Alert | None: ...
    async def list_alerts_for_user(self, user_id: str) -> list[Alert]: ...
    async def get_active_alert_by_dedup_key(self, dedup_key: str) -> Alert | None: ...

    async def save_evaluation_run(self, run: EvaluationRun) -> EvaluationRun: ...
    async def list_evaluation_runs_for_monitor(self, monitor_id: str) -> list[EvaluationRun]: ...


class PostgresSystemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_monitor(self, monitor: MonitorDefinition) -> MonitorDefinition:
        row = await self._session.get(MonitorDefinitionRow, monitor.monitor_id)
        if row is None:
            row = MonitorDefinitionRow(
                monitor_id=monitor.monitor_id,
                user_id=monitor.user_id,
                monitor_type=monitor.monitor_type.value,
                created_at=monitor.created_at,
            )
            self._session.add(row)
        row.enabled = monitor.enabled
        row.quiet_hours_start_utc = monitor.quiet_hours_start_utc
        row.quiet_hours_end_utc = monitor.quiet_hours_end_utc
        row.updated_at = monitor.updated_at
        await self._session.flush()
        return monitor

    async def get_monitor(self, monitor_id: str) -> MonitorDefinition | None:
        row = await self._session.get(MonitorDefinitionRow, monitor_id)
        return _row_to_monitor(row) if row is not None else None

    async def list_monitors_for_user(self, user_id: str) -> list[MonitorDefinition]:
        result = await self._session.execute(
            select(MonitorDefinitionRow).where(MonitorDefinitionRow.user_id == user_id)
        )
        return [_row_to_monitor(row) for row in result.scalars().all()]

    async def list_all_enabled_monitors(self) -> list[MonitorDefinition]:
        """No Identity domain exists to enumerate users — the scheduled
        sweep (`application/orchestrators/monitoring.py`) discovers who to
        evaluate by which users have any enabled monitor on record at all,
        the same pragmatic convention this codebase already uses elsewhere
        for a single-user-system-in-practice with no real multi-tenant
        Identity domain yet."""
        result = await self._session.execute(
            select(MonitorDefinitionRow).where(MonitorDefinitionRow.enabled.is_(True))
        )
        return [_row_to_monitor(row) for row in result.scalars().all()]

    async def save_alert(self, alert: Alert) -> Alert:
        row = await self._session.get(AlertRow, alert.alert_id)
        if row is None:
            row = AlertRow(
                alert_id=alert.alert_id,
                monitor_id=alert.monitor_id,
                user_id=alert.user_id,
                monitor_type=alert.monitor_type.value,
                message=alert.message,
                reason=alert.reason,
                dedup_key=alert.dedup_key,
                triggered_at=alert.triggered_at,
                created_during_quiet_hours=alert.created_during_quiet_hours,
            )
            self._session.add(row)
        row.severity = alert.severity.value
        row.status = alert.status.value
        row.acknowledged_at = alert.acknowledged_at
        await self._session.flush()
        return alert

    async def get_alert(self, alert_id: str) -> Alert | None:
        row = await self._session.get(AlertRow, alert_id)
        return _row_to_alert(row) if row is not None else None

    async def list_alerts_for_user(self, user_id: str) -> list[Alert]:
        result = await self._session.execute(select(AlertRow).where(AlertRow.user_id == user_id))
        return [_row_to_alert(row) for row in result.scalars().all()]

    async def get_active_alert_by_dedup_key(self, dedup_key: str) -> Alert | None:
        result = await self._session.execute(
            select(AlertRow).where(
                AlertRow.dedup_key == dedup_key, AlertRow.status == AlertStatus.ACTIVE.value
            )
        )
        row = result.scalars().first()
        return _row_to_alert(row) if row is not None else None

    async def save_evaluation_run(self, run: EvaluationRun) -> EvaluationRun:
        # Immutable/append-only — always an insert, matching
        # domains/projects/repository.py's Decision/StatusUpdate precedent.
        self._session.add(
            EvaluationRunRow(
                evaluation_id=run.evaluation_id,
                monitor_id=run.monitor_id,
                user_id=run.user_id,
                monitor_type=run.monitor_type.value,
                evaluated_at=run.evaluated_at,
                triggered=run.triggered,
                detail=run.detail,
            )
        )
        await self._session.flush()
        return run

    async def list_evaluation_runs_for_monitor(self, monitor_id: str) -> list[EvaluationRun]:
        result = await self._session.execute(
            select(EvaluationRunRow).where(EvaluationRunRow.monitor_id == monitor_id)
        )
        return [_row_to_evaluation_run(row) for row in result.scalars().all()]
