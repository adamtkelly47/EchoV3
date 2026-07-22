"""API-boundary request/response schemas — never the application/domain
layer's own TrustDashboardView/HallucinationIncident crossing the wire
directly (CONSTITUTION.md: Typed Contracts), matching every other
apps/api/schemas/*.py convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RateMetricResponse(BaseModel):
    successes: int
    total: int
    rate: float | None


class CostMetricResponse(BaseModel):
    total_usd: float
    call_count: int


class LatencyMetricResponse(BaseModel):
    avg_ms: float | None
    p95_ms: float | None
    sample_count: int


class FreshnessStatusResponse(BaseModel):
    status: str
    as_of: datetime | None


class ReconciliationStatusResponse(BaseModel):
    status: str
    reconciliation_diff: float | None
    as_of: datetime | None


class IntegrationUptimeEntryResponse(BaseModel):
    name: str
    successes: int
    failures: int
    uptime_rate: float | None


class TrustDashboardResponse(BaseModel):
    user_id: str
    generated_at: datetime
    window_start: datetime
    tool_accuracy: RateMetricResponse
    calculation_reconciliation: ReconciliationStatusResponse
    data_freshness: FreshnessStatusResponse
    local_model_schema_success: RateMetricResponse
    local_model_classification_quality: RateMetricResponse
    claude_escalation_rate: RateMetricResponse
    hallucination_incidents_open: int
    hallucination_incidents_resolved: int
    approval_bypass_attempts_blocked: int
    execution_verification_rate: RateMetricResponse
    integration_uptime: list[IntegrationUptimeEntryResponse]
    user_corrections: int
    regression_case_count: int
    cost: CostMetricResponse
    latency: LatencyMetricResponse


class ReportHallucinationRequest(BaseModel):
    user_id: str
    description: str
    correlation_id: str | None = None


class ResolveHallucinationRequest(BaseModel):
    resolution_note: str


class HallucinationIncidentResponse(BaseModel):
    incident_id: str
    user_id: str
    correlation_id: str | None
    description: str
    status: str
    reported_at: datetime
    resolution_note: str | None
    resolved_at: datetime | None


class RecordUserCorrectionRequest(BaseModel):
    content: str
    confidence: float
    correlation_id: str | None = None


class RegressionCaseResponse(BaseModel):
    case_id: str
    source_type: str
    source_id: str
    incorrect_output: str
    corrected_output: str
    created_at: datetime
