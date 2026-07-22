"""PROMPT.md Phase 25: "Measure whether Echo is actually becoming
reliable." A second Application-layer query (the first was Phase 22's
`DashboardQueryService`) — read-only, cross-domain, no writes. It computes
Phase 25's 13 tracked items entirely from signals that already exist
elsewhere in this codebase:

- Tool accuracy, execution verification rate, latency: `tool_calls`
  (`infrastructure/database/repositories/observability.py`), populated by
  `domains/capabilities/service.py`'s `CapabilityExecutor` since Phase 8.
- Local model schema success, classification quality, Claude escalation
  rate, cost, latency: `model_calls`, populated for the first time this
  phase by `providers/models/gateway.py`'s `ModelGateway` (see Docs/
  DECISION_LOG.md's Phase 25 entry — the table and repository existed
  since Phase 7 but nothing ever wrote to them until now).
- Calculation reconciliation, data freshness: `PortfolioService.
  get_dashboard`'s already-computed `reconciled`/`is_stale` fields
  (Phase 13), the same call Phase 22's dashboard already makes.
- Integration uptime: `calendar.token_refreshed`/`token_refresh_failed`
  and `schwab.token_refreshed`/`token_refresh_failed` audit actions
  (Phases 10-12), the same actions Phase 24's "integration failure"
  monitor already reuses.
- Approval bypass attempts blocked: `approval.execution_blocked_not_
  approved`, a new audit action added this phase to `domains/approvals/
  service.py`'s `execute()` — every other rejection branch there already
  recorded one; this was the one real gap.
- User corrections: `memory.superseded` audit events with
  `detail["source_type"] == "user_correction"` — the convention
  `application/orchestrators/trust.py`'s `TrustOrchestrator` establishes.
- Hallucination incidents: `domains/system/service.py`'s new
  `HallucinationIncident` records (a human-reported concept — no automatic
  detector exists or is claimed).

"Local model classification quality" is honestly a structural proxy (schema
success rate filtered to `TaskType.CLASSIFICATION`), not a labeled
ground-truth eval — this codebase has no labeled classification eval set.
`RegressionCase` (built from resolved hallucination incidents and user
corrections) is the seed of a real one; running evaluations against it is
future work, not claimed here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from core.time import Clock
from domains.portfolio.service import PortfolioService
from domains.system.models import HallucinationIncidentStatus
from domains.system.service import SystemService
from infrastructure.database.repositories.audit import AuditRepository
from infrastructure.database.repositories.observability import (
    ModelCallRepository,
    ToolCallRepository,
)
from providers.models.contracts import TaskType

_DEFAULT_WINDOW = timedelta(days=7)
_INTEGRATION_AUDIT_ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("Google Calendar", "calendar.token_refreshed", "calendar.token_refresh_failed"),
    ("Schwab", "schwab.token_refreshed", "schwab.token_refresh_failed"),
)


class RateMetric(BaseModel):
    successes: int
    total: int
    rate: float | None

    @classmethod
    def of(cls, successes: int, total: int) -> RateMetric:
        return cls(successes=successes, total=total, rate=(successes / total if total else None))


class CostMetric(BaseModel):
    total_usd: float
    call_count: int


class LatencyMetric(BaseModel):
    avg_ms: float | None
    p95_ms: float | None
    sample_count: int


class FreshnessStatus(BaseModel):
    status: Literal["ok", "stale", "not_connected", "no_data"]
    as_of: datetime | None


class ReconciliationStatus(BaseModel):
    status: Literal["reconciled", "discrepancy", "not_connected", "no_data"]
    reconciliation_diff: float | None
    as_of: datetime | None


class IntegrationUptimeEntry(BaseModel):
    name: str
    successes: int
    failures: int
    uptime_rate: float | None


class TrustDashboardView(BaseModel):
    user_id: str
    generated_at: datetime
    window_start: datetime
    tool_accuracy: RateMetric
    calculation_reconciliation: ReconciliationStatus
    data_freshness: FreshnessStatus
    local_model_schema_success: RateMetric
    local_model_classification_quality: RateMetric
    claude_escalation_rate: RateMetric
    hallucination_incidents_open: int
    hallucination_incidents_resolved: int
    approval_bypass_attempts_blocked: int
    execution_verification_rate: RateMetric
    integration_uptime: list[IntegrationUptimeEntry]
    user_corrections: int
    regression_case_count: int
    cost: CostMetric
    latency: LatencyMetric


class TrustDashboardQueryService:
    def __init__(
        self,
        portfolio: PortfolioService,
        system: SystemService,
        audit: AuditRepository,
        model_calls: ModelCallRepository,
        tool_calls: ToolCallRepository,
        clock: Clock,
    ) -> None:
        self._portfolio = portfolio
        self._system = system
        self._audit = audit
        self._model_calls = model_calls
        self._tool_calls = tool_calls
        self._clock = clock

    async def build(
        self, user_id: str, *, window: timedelta = _DEFAULT_WINDOW
    ) -> TrustDashboardView:
        now = self._clock.now_utc()
        window_start = now - window

        tool_rows = await self._tool_calls.list_since(window_start)
        model_rows = await self._model_calls.list_since(window_start)

        tool_accuracy = RateMetric.of(
            sum(1 for r in tool_rows if r.status == "success"), len(tool_rows)
        )
        # "Execution verification rate" reads domains/approvals/service.py's
        # own real post-execution verifier outcome
        # (`_run_execution`'s `ExecutionVerifier.verify()` call) rather than
        # `ToolCallRow.approval_check_passed` — that column exists in the
        # schema but no caller has ever populated it (CapabilityExecutor
        # only records tool calls, never consequential/approved ones), so
        # it would always be an empty, misleadingly-named "no data" here.
        executed_rows = await self._audit.list_recent_by_action("approval.executed", window_start)
        verification_failed_rows = await self._audit.list_recent_by_action(
            "approval.verification_failed", window_start
        )
        execution_verification_rate = RateMetric.of(
            len(executed_rows), len(executed_rows) + len(verification_failed_rows)
        )

        structured_rows = [r for r in model_rows if r.schema_valid is not None]
        local_model_schema_success = RateMetric.of(
            sum(1 for r in structured_rows if r.schema_valid), len(structured_rows)
        )
        classification_rows = [
            r for r in structured_rows if r.task_type == TaskType.CLASSIFICATION.value
        ]
        local_model_classification_quality = RateMetric.of(
            sum(1 for r in classification_rows if r.schema_valid), len(classification_rows)
        )
        claude_escalation_rate = RateMetric.of(
            sum(1 for r in model_rows if r.escalated), len(model_rows)
        )
        cost = CostMetric(
            total_usd=sum(r.cost_estimate_usd or 0.0 for r in model_rows),
            call_count=len(model_rows),
        )
        all_latencies = [r.latency_ms for r in tool_rows if r.latency_ms is not None] + [
            r.latency_ms for r in model_rows if r.latency_ms is not None
        ]
        latency = _latency_metric(all_latencies)

        bypass_rows = await self._audit.list_recent_by_action(
            "approval.execution_blocked_not_approved", window_start
        )
        correction_rows = [
            row
            for row in await self._audit.list_recent_by_action("memory.superseded", window_start)
            if (row.detail or {}).get("source_type") == "user_correction"
        ]

        hallucinations = await self._system.list_hallucination_incidents_since(window_start)
        regression_cases = await self._system.list_regression_cases()

        integration_uptime = [
            await self._integration_uptime(name, success_action, failure_action, window_start)
            for name, success_action, failure_action in _INTEGRATION_AUDIT_ACTIONS
        ]

        return TrustDashboardView(
            user_id=user_id,
            generated_at=now,
            window_start=window_start,
            tool_accuracy=tool_accuracy,
            calculation_reconciliation=await self._reconciliation(user_id),
            data_freshness=await self._freshness(user_id),
            local_model_schema_success=local_model_schema_success,
            local_model_classification_quality=local_model_classification_quality,
            claude_escalation_rate=claude_escalation_rate,
            hallucination_incidents_open=sum(
                1 for h in hallucinations if h.status == HallucinationIncidentStatus.OPEN
            ),
            hallucination_incidents_resolved=sum(
                1 for h in hallucinations if h.status == HallucinationIncidentStatus.RESOLVED
            ),
            approval_bypass_attempts_blocked=len(bypass_rows),
            execution_verification_rate=execution_verification_rate,
            integration_uptime=integration_uptime,
            user_corrections=len(correction_rows),
            regression_case_count=len(regression_cases),
            cost=cost,
            latency=latency,
        )

    async def _reconciliation(self, user_id: str) -> ReconciliationStatus:
        if not await self._portfolio.is_connected(user_id):
            return ReconciliationStatus(
                status="not_connected", reconciliation_diff=None, as_of=None
            )
        snapshot = await self._portfolio.get_latest_snapshot(user_id)
        if snapshot is None:
            return ReconciliationStatus(status="no_data", reconciliation_diff=None, as_of=None)
        return ReconciliationStatus(
            status="reconciled" if snapshot.reconciled else "discrepancy",
            reconciliation_diff=snapshot.reconciliation_diff,
            as_of=snapshot.taken_at,
        )

    async def _freshness(self, user_id: str) -> FreshnessStatus:
        if not await self._portfolio.is_connected(user_id):
            return FreshnessStatus(status="not_connected", as_of=None)
        snapshot = await self._portfolio.get_latest_snapshot(user_id)
        if snapshot is None:
            return FreshnessStatus(status="no_data", as_of=None)
        dashboard = await self._portfolio.get_dashboard(user_id)
        return FreshnessStatus(
            status="stale" if dashboard.is_stale else "ok", as_of=snapshot.taken_at
        )

    async def _integration_uptime(
        self, name: str, success_action: str, failure_action: str, since: datetime
    ) -> IntegrationUptimeEntry:
        successes = len(await self._audit.list_recent_by_action(success_action, since))
        failures = len(await self._audit.list_recent_by_action(failure_action, since))
        total = successes + failures
        return IntegrationUptimeEntry(
            name=name,
            successes=successes,
            failures=failures,
            uptime_rate=(successes / total if total else None),
        )


def _latency_metric(values: list[float]) -> LatencyMetric:
    if not values:
        return LatencyMetric(avg_ms=None, p95_ms=None, sample_count=0)
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return LatencyMetric(
        avg_ms=sum(ordered) / len(ordered),
        p95_ms=ordered[p95_index],
        sample_count=len(ordered),
    )
