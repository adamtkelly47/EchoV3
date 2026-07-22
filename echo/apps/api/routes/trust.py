"""PROMPT.md Phase 25: the evaluation/trust dashboard's read endpoint, plus
the two write paths that feed its "corrected failures" regression dataset
(hallucination incidents, user-initiated memory corrections). No
authentication/Identity domain exists yet — `user_id` is accepted directly
in the request body/query params, matching every other routes module's
documented convention for this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.trust import TrustOrchestrator
from application.queries.trust_dashboard_query import (
    CostMetric,
    FreshnessStatus,
    IntegrationUptimeEntry,
    LatencyMetric,
    RateMetric,
    ReconciliationStatus,
    TrustDashboardQueryService,
    TrustDashboardView,
)
from apps.api.dependencies import (
    get_db_session,
    get_system_service,
    get_trust_dashboard_query_service,
    get_trust_orchestrator,
)
from apps.api.schemas.trust import (
    CostMetricResponse,
    FreshnessStatusResponse,
    HallucinationIncidentResponse,
    IntegrationUptimeEntryResponse,
    LatencyMetricResponse,
    RateMetricResponse,
    ReconciliationStatusResponse,
    RecordUserCorrectionRequest,
    RegressionCaseResponse,
    ReportHallucinationRequest,
    ResolveHallucinationRequest,
    TrustDashboardResponse,
)
from domains.system.schemas import HallucinationIncident, RegressionCase
from domains.system.service import SystemService

router = APIRouter(prefix="/trust", tags=["trust"])


def _to_rate_response(metric: RateMetric) -> RateMetricResponse:
    return RateMetricResponse(successes=metric.successes, total=metric.total, rate=metric.rate)


def _to_cost_response(metric: CostMetric) -> CostMetricResponse:
    return CostMetricResponse(total_usd=metric.total_usd, call_count=metric.call_count)


def _to_latency_response(metric: LatencyMetric) -> LatencyMetricResponse:
    return LatencyMetricResponse(
        avg_ms=metric.avg_ms, p95_ms=metric.p95_ms, sample_count=metric.sample_count
    )


def _to_freshness_response(status: FreshnessStatus) -> FreshnessStatusResponse:
    return FreshnessStatusResponse(status=status.status, as_of=status.as_of)


def _to_reconciliation_response(status: ReconciliationStatus) -> ReconciliationStatusResponse:
    return ReconciliationStatusResponse(
        status=status.status,
        reconciliation_diff=status.reconciliation_diff,
        as_of=status.as_of,
    )


def _to_integration_uptime_response(
    entry: IntegrationUptimeEntry,
) -> IntegrationUptimeEntryResponse:
    return IntegrationUptimeEntryResponse(
        name=entry.name,
        successes=entry.successes,
        failures=entry.failures,
        uptime_rate=entry.uptime_rate,
    )


def _to_dashboard_response(view: TrustDashboardView) -> TrustDashboardResponse:
    return TrustDashboardResponse(
        user_id=view.user_id,
        generated_at=view.generated_at,
        window_start=view.window_start,
        tool_accuracy=_to_rate_response(view.tool_accuracy),
        calculation_reconciliation=_to_reconciliation_response(view.calculation_reconciliation),
        data_freshness=_to_freshness_response(view.data_freshness),
        local_model_schema_success=_to_rate_response(view.local_model_schema_success),
        local_model_classification_quality=_to_rate_response(
            view.local_model_classification_quality
        ),
        claude_escalation_rate=_to_rate_response(view.claude_escalation_rate),
        hallucination_incidents_open=view.hallucination_incidents_open,
        hallucination_incidents_resolved=view.hallucination_incidents_resolved,
        approval_bypass_attempts_blocked=view.approval_bypass_attempts_blocked,
        execution_verification_rate=_to_rate_response(view.execution_verification_rate),
        integration_uptime=[_to_integration_uptime_response(e) for e in view.integration_uptime],
        user_corrections=view.user_corrections,
        regression_case_count=view.regression_case_count,
        cost=_to_cost_response(view.cost),
        latency=_to_latency_response(view.latency),
    )


def _to_incident_response(incident: HallucinationIncident) -> HallucinationIncidentResponse:
    return HallucinationIncidentResponse(
        incident_id=incident.incident_id,
        user_id=incident.user_id,
        correlation_id=incident.correlation_id,
        description=incident.description,
        status=incident.status.value,
        reported_at=incident.reported_at,
        resolution_note=incident.resolution_note,
        resolved_at=incident.resolved_at,
    )


def _to_regression_case_response(case: RegressionCase) -> RegressionCaseResponse:
    return RegressionCaseResponse(
        case_id=case.case_id,
        source_type=case.source_type,
        source_id=case.source_id,
        incorrect_output=case.incorrect_output,
        corrected_output=case.corrected_output,
        created_at=case.created_at,
    )


@router.get("/dashboard", response_model=TrustDashboardResponse)
async def get_trust_dashboard(
    user_id: str, dashboard: TrustDashboardQueryService = Depends(get_trust_dashboard_query_service)
) -> TrustDashboardResponse:
    view = await dashboard.build(user_id)
    return _to_dashboard_response(view)


@router.post("/hallucination-incidents", response_model=HallucinationIncidentResponse)
async def report_hallucination(
    body: ReportHallucinationRequest,
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> HallucinationIncidentResponse:
    incident = await system.report_hallucination(
        body.user_id, description=body.description, correlation_id=body.correlation_id
    )
    await session.commit()
    return _to_incident_response(incident)


@router.get("/hallucination-incidents", response_model=list[HallucinationIncidentResponse])
async def list_hallucination_incidents(
    user_id: str, system: SystemService = Depends(get_system_service)
) -> list[HallucinationIncidentResponse]:
    incidents = await system.list_hallucination_incidents_for_user(user_id)
    return [_to_incident_response(i) for i in incidents]


@router.post(
    "/hallucination-incidents/{incident_id}/resolve", response_model=HallucinationIncidentResponse
)
async def resolve_hallucination(
    incident_id: str,
    body: ResolveHallucinationRequest,
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> HallucinationIncidentResponse:
    incident = await system.resolve_hallucination(incident_id, resolution_note=body.resolution_note)
    await session.commit()
    return _to_incident_response(incident)


@router.post("/corrections/{memory_id}", response_model=RegressionCaseResponse)
async def record_user_correction(
    memory_id: str,
    body: RecordUserCorrectionRequest,
    trust: TrustOrchestrator = Depends(get_trust_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> RegressionCaseResponse:
    _memory, case = await trust.record_user_correction(
        memory_id,
        content=body.content,
        confidence=body.confidence,
        correlation_id=body.correlation_id,
    )
    await session.commit()
    return _to_regression_case_response(case)


@router.get("/regression-cases", response_model=list[RegressionCaseResponse])
async def list_regression_cases(
    system: SystemService = Depends(get_system_service),
) -> list[RegressionCaseResponse]:
    cases = await system.list_regression_cases()
    return [_to_regression_case_response(c) for c in cases]
