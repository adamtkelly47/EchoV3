"""Uses real Portfolio/System services backed by fakes, matching
tests/unit/application/queries/test_dashboard_query.py's own pattern —
proves the aggregation wiring against the actual domain services, not a
re-implementation of them.
"""

from datetime import UTC, datetime, timedelta

from application.queries.trust_dashboard_query import TrustDashboardQueryService
from core.time import FakeClock
from domains.portfolio.schemas import PortfolioSnapshot
from domains.portfolio.service import PortfolioService
from domains.system.models import MonitorType
from domains.system.service import SystemService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.application.queries.fakes import (
    FakeModelCallRepository,
    FakeObservabilityAuditRepository,
    FakeToolCallRepository,
)
from tests.unit.domains.portfolio.fakes import FakeAuditRepository as FakePortfolioAuditRepository
from tests.unit.domains.portfolio.fakes import (
    FakeComplianceResultRepository,
    FakeComputedValueRecordRepository,
    FakeHypotheticalTradeRepository,
    FakeIPSRepository,
    FakePortfolioRepository,
    FakeSchwabCredentialRepository,
    FakeSchwabProvider,
)
from tests.unit.domains.portfolio.fakes import (
    FakeSourceRecordRepository as FakePortfolioSourceRecordRepository,
)
from tests.unit.domains.system.fakes import FakeAuditRepository as FakeSystemOwnAuditRepository
from tests.unit.domains.system.fakes import FakeSystemRepository

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _query_service(
    clock: FakeClock,
) -> tuple[
    TrustDashboardQueryService,
    PortfolioService,
    FakePortfolioRepository,
    SystemService,
    FakeObservabilityAuditRepository,
    FakeModelCallRepository,
    FakeToolCallRepository,
]:
    portfolio_repo = FakePortfolioRepository()
    portfolio = PortfolioService(
        FakeSchwabCredentialRepository(),
        portfolio_repo,
        FakePortfolioSourceRecordRepository(),
        FakeSchwabProvider(),
        SecretCipher(_FERNET_KEY),
        FakePortfolioAuditRepository(),
        clock,
        "state-secret",
        FakeComputedValueRecordRepository(),
        FakeIPSRepository(),
        FakeComplianceResultRepository(),
        FakeHypotheticalTradeRepository(),
    )
    system = SystemService(FakeSystemRepository(), FakeSystemOwnAuditRepository(), clock)
    audit = FakeObservabilityAuditRepository()
    model_calls = FakeModelCallRepository()
    tool_calls = FakeToolCallRepository()
    query = TrustDashboardQueryService(portfolio, system, audit, model_calls, tool_calls, clock)
    return query, portfolio, portfolio_repo, system, audit, model_calls, tool_calls


async def test_reconciliation_and_freshness_are_not_connected_when_no_credential() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, *_ = _query_service(clock)
    view = await query.build("user_1")
    assert view.calculation_reconciliation.status == "not_connected"
    assert view.data_freshness.status == "not_connected"


async def test_reconciliation_and_freshness_reflect_a_real_snapshot() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, portfolio, portfolio_repo, *_ = _query_service(clock)
    state = portfolio.start_authorization("user_1")
    state_value = state.split("state=", 1)[1]
    await portfolio.complete_authorization("auth-code", state_value)
    portfolio_repo.snapshots.append(
        PortfolioSnapshot(
            user_id="user_1",
            taken_at=clock.now_utc(),
            total_market_value=1000.0,
            reconciled=True,
            reconciliation_diff=0.0,
            account_ids=["account_1"],
            warnings=[],
        )
    )
    view = await query.build("user_1")
    assert view.calculation_reconciliation.status == "reconciled"
    assert view.data_freshness.status == "ok"


async def test_reconciliation_reports_discrepancy_when_snapshot_is_unreconciled() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, portfolio, portfolio_repo, *_ = _query_service(clock)
    state = portfolio.start_authorization("user_1")
    state_value = state.split("state=", 1)[1]
    await portfolio.complete_authorization("auth-code", state_value)
    portfolio_repo.snapshots.append(
        PortfolioSnapshot(
            user_id="user_1",
            taken_at=clock.now_utc(),
            total_market_value=1000.0,
            reconciled=False,
            reconciliation_diff=12.5,
            account_ids=["account_1"],
            warnings=[],
        )
    )
    view = await query.build("user_1")
    assert view.calculation_reconciliation.status == "discrepancy"
    assert view.calculation_reconciliation.reconciliation_diff == 12.5


async def test_model_call_metrics_are_computed_from_real_recorded_calls() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, _, model_calls, _ = _query_service(clock)
    await model_calls.record(
        provider="ollama",
        model_name="m",
        task_type="classification",
        schema_valid=True,
        cost_estimate_usd=0.0,
        latency_ms=10.0,
    )
    await model_calls.record(
        provider="ollama",
        model_name="m",
        task_type="classification",
        schema_valid=False,
        cost_estimate_usd=0.0,
        latency_ms=20.0,
    )
    await model_calls.record(
        provider="claude",
        model_name="m",
        task_type="synthesis",
        escalated=True,
        cost_estimate_usd=0.05,
        latency_ms=100.0,
    )
    view = await query.build("user_1")
    assert view.local_model_schema_success.successes == 1
    assert view.local_model_schema_success.total == 2
    assert view.local_model_classification_quality.total == 2
    assert view.claude_escalation_rate.successes == 1
    assert view.claude_escalation_rate.total == 3
    assert view.cost.total_usd == 0.05
    assert view.cost.call_count == 3
    assert view.latency.sample_count == 3


async def test_tool_accuracy_is_computed_from_real_recorded_tool_calls() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, _, _, tool_calls = _query_service(clock)
    await tool_calls.record(
        capability_id="c", capability_version=1, permission_check_passed=True, status="success"
    )
    await tool_calls.record(
        capability_id="c", capability_version=1, permission_check_passed=True, status="failure"
    )
    view = await query.build("user_1")
    assert view.tool_accuracy.successes == 1
    assert view.tool_accuracy.total == 2


async def test_approval_bypass_attempts_are_counted_from_the_blocked_audit_action() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, audit, _, _ = _query_service(clock)
    await audit.record(action="approval.execution_blocked_not_approved", result="blocked")
    await audit.record(action="approval.execution_blocked_not_approved", result="blocked")
    view = await query.build("user_1")
    assert view.approval_bypass_attempts_blocked == 2


async def test_execution_verification_rate_reads_real_approval_audit_actions() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, audit, _, _ = _query_service(clock)
    await audit.record(action="approval.executed", result="success")
    await audit.record(action="approval.executed", result="success")
    await audit.record(action="approval.verification_failed", result="failure")
    view = await query.build("user_1")
    assert view.execution_verification_rate.successes == 2
    assert view.execution_verification_rate.total == 3


async def test_user_corrections_are_counted_only_for_the_user_correction_source_type() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, audit, _, _ = _query_service(clock)
    await audit.record(
        action="memory.superseded",
        result="success",
        detail={"source_type": "user_correction"},
    )
    await audit.record(
        action="memory.superseded",
        result="success",
        detail={"source_type": "project_decision"},
    )
    view = await query.build("user_1")
    assert view.user_corrections == 1


async def test_integration_uptime_reads_real_success_and_failure_audit_actions() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, audit, _, _ = _query_service(clock)
    await audit.record(action="calendar.token_refreshed", result="success")
    await audit.record(action="calendar.token_refreshed", result="success")
    await audit.record(action="calendar.token_refresh_failed", result="failure")
    view = await query.build("user_1")
    calendar_entry = next(e for e in view.integration_uptime if e.name == "Google Calendar")
    assert calendar_entry.successes == 2
    assert calendar_entry.failures == 1
    assert calendar_entry.uptime_rate == 2 / 3


async def test_hallucination_and_regression_counts_reflect_real_system_records() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, system, _, _, _ = _query_service(clock)
    monitor_before = await system.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    assert monitor_before is not None  # sanity: system domain is wired up

    incident = await system.report_hallucination("user_1", description="wrong claim")
    await system.resolve_hallucination(incident.incident_id, resolution_note="correct answer")
    open_incident = await system.report_hallucination("user_1", description="another wrong claim")
    assert open_incident is not None

    view = await query.build("user_1")
    assert view.hallucination_incidents_open == 1
    assert view.hallucination_incidents_resolved == 1
    assert view.regression_case_count == 1


async def test_window_defaults_do_not_exclude_recent_calls() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    query, _, _, _, _, model_calls, _ = _query_service(clock)
    await model_calls.record(provider="ollama", model_name="m", task_type="conversation")
    view = await query.build("user_1", window=timedelta(days=1))
    assert view.cost.call_count == 1
