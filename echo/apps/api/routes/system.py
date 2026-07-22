"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in the request body/query params, matching every other routes
module's documented convention for this phase. `POST /monitors/evaluate`
exists so the real evaluation sweep can be exercised on demand (live
verification, manual testing) — the actual scheduled path is
`apps/scheduler/main.py` enqueuing a `monitoring.evaluate` job the worker
consumes (PROMPT.md Phase 24 implement item 2: "trigger schedules").
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.monitoring import MonitoringOrchestrator
from apps.api.dependencies import (
    get_db_session,
    get_monitoring_orchestrator,
    get_system_service,
)
from apps.api.schemas.system import (
    AlertResponse,
    CreateMonitorRequest,
    EvaluationRunResponse,
    MonitorResponse,
    SetMonitorEnabledRequest,
)
from domains.system.models import MonitorType
from domains.system.schemas import Alert, EvaluationRun, MonitorDefinition
from domains.system.service import SystemService

router = APIRouter(prefix="/monitors", tags=["system"])


def _to_monitor_response(monitor: MonitorDefinition) -> MonitorResponse:
    return MonitorResponse(
        monitor_id=monitor.monitor_id,
        user_id=monitor.user_id,
        monitor_type=monitor.monitor_type.value,
        enabled=monitor.enabled,
        quiet_hours_start_utc=monitor.quiet_hours_start_utc,
        quiet_hours_end_utc=monitor.quiet_hours_end_utc,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
    )


def _to_alert_response(alert: Alert) -> AlertResponse:
    return AlertResponse(
        alert_id=alert.alert_id,
        monitor_id=alert.monitor_id,
        user_id=alert.user_id,
        monitor_type=alert.monitor_type.value,
        severity=alert.severity.value,
        message=alert.message,
        reason=alert.reason,
        status=alert.status.value,
        triggered_at=alert.triggered_at,
        created_during_quiet_hours=alert.created_during_quiet_hours,
        acknowledged_at=alert.acknowledged_at,
    )


def _to_evaluation_run_response(run: EvaluationRun) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        evaluation_id=run.evaluation_id,
        monitor_id=run.monitor_id,
        user_id=run.user_id,
        monitor_type=run.monitor_type.value,
        evaluated_at=run.evaluated_at,
        triggered=run.triggered,
        detail=run.detail,
    )


@router.post("", response_model=MonitorResponse)
async def create_monitor(
    body: CreateMonitorRequest,
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    monitor = await system.create_monitor(
        body.user_id,
        MonitorType(body.monitor_type),
        quiet_hours_start_utc=body.quiet_hours_start_utc,
        quiet_hours_end_utc=body.quiet_hours_end_utc,
    )
    await session.commit()
    return _to_monitor_response(monitor)


@router.get("", response_model=list[MonitorResponse])
async def list_monitors(
    user_id: str, system: SystemService = Depends(get_system_service)
) -> list[MonitorResponse]:
    monitors = await system.list_monitors_for_user(user_id)
    return [_to_monitor_response(m) for m in monitors]


@router.patch("/{monitor_id}/enabled", response_model=MonitorResponse)
async def set_monitor_enabled(
    monitor_id: str,
    body: SetMonitorEnabledRequest,
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> MonitorResponse:
    """PROMPT.md Phase 24 verification 4: "users can disable a monitor.\" """
    monitor = await system.set_monitor_enabled(monitor_id, body.enabled)
    await session.commit()
    return _to_monitor_response(monitor)


@router.get("/{monitor_id}/evaluations", response_model=list[EvaluationRunResponse])
async def list_evaluation_runs(
    monitor_id: str, system: SystemService = Depends(get_system_service)
) -> list[EvaluationRunResponse]:
    """PROMPT.md Phase 24 implement item 10: "evaluation audit.\" """
    runs = await system.list_evaluation_runs_for_monitor(monitor_id)
    return [_to_evaluation_run_response(r) for r in runs]


@router.post("/evaluate", response_model=list[EvaluationRunResponse])
async def evaluate_all_monitors(
    orchestrator: MonitoringOrchestrator = Depends(get_monitoring_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> list[EvaluationRunResponse]:
    runs = await orchestrator.evaluate_all_enabled_monitors()
    await session.commit()
    return [_to_evaluation_run_response(r) for r in runs]


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    user_id: str, system: SystemService = Depends(get_system_service)
) -> list[AlertResponse]:
    alerts = await system.list_alerts_for_user(user_id)
    return [_to_alert_response(a) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> AlertResponse:
    """PROMPT.md Phase 24 implement item 8: "alert acknowledgement.\" """
    alert = await system.acknowledge_alert(alert_id)
    await session.commit()
    return _to_alert_response(alert)


@router.post("/alerts/{alert_id}/suppress", response_model=AlertResponse)
async def suppress_alert(
    alert_id: str,
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> AlertResponse:
    """PROMPT.md Phase 24 implement item 9: "alert suppression.\" """
    alert = await system.suppress_alert(alert_id)
    await session.commit()
    return _to_alert_response(alert)
