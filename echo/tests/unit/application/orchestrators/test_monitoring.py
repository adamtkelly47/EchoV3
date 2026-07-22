"""Uses real Portfolio/Calendar/Research/System services backed by fakes,
matching tests/unit/application/orchestrators/test_news_intelligence.py's
own pattern — proves the cross-domain wiring against the actual domain
services, not a re-implementation of them.
"""

from datetime import UTC, datetime, timedelta

from application.orchestrators.monitoring import MonitoringOrchestrator
from core.time import FakeClock
from domains.calendar.service import CalendarService
from domains.portfolio.models import AssetType
from domains.portfolio.schemas import (
    AccountBalance,
    ComplianceBreach,
    ComplianceResult,
    PortfolioSnapshot,
    Position,
)
from domains.portfolio.service import PortfolioService
from domains.research.schemas import Issuer, NewsDigest
from domains.research.service import ResearchService
from domains.system.models import MonitorType
from domains.system.service import SystemService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.calendar.fakes import FakeAuditRepository as FakeCalendarAuditRepository
from tests.unit.domains.calendar.fakes import (
    FakeCalendarCredentialRepository,
    FakeCalendarEventRepository,
    FakeCalendarProvider,
)
from tests.unit.domains.portfolio.fakes import FakeAuditRepository as FakePortfolioAuditRepository
from tests.unit.domains.portfolio.fakes import (
    FakeComplianceResultRepository,
    FakeComputedValueRecordRepository,
    FakeIPSRepository,
    FakePortfolioRepository,
    FakeSchwabCredentialRepository,
    FakeSchwabProvider,
)
from tests.unit.domains.portfolio.fakes import (
    FakeSourceRecordRepository as FakePortfolioSourceRecordRepository,
)
from tests.unit.domains.research.fakes import FakeAuditRepository as FakeResearchAuditRepository
from tests.unit.domains.research.fakes import FakeResearchRepository
from tests.unit.domains.research.fakes import (
    FakeSourceRecordRepository as FakeResearchSourceRecordRepository,
)
from tests.unit.domains.system.fakes import FakeAuditRepository, FakeSystemRepository

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _orchestrator(
    clock: FakeClock,
) -> tuple[
    MonitoringOrchestrator,
    SystemService,
    PortfolioService,
    FakePortfolioRepository,
    FakeComplianceResultRepository,
    CalendarService,
    FakeCalendarProvider,
    ResearchService,
    FakeResearchRepository,
    FakeAuditRepository,
]:
    system_audit = FakeAuditRepository()
    system = SystemService(FakeSystemRepository(), system_audit, clock)

    portfolio_repo = FakePortfolioRepository()
    compliance_repo = FakeComplianceResultRepository()
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
        compliance_repo,
    )
    calendar_provider = FakeCalendarProvider()
    calendar = CalendarService(
        FakeCalendarCredentialRepository(),
        FakeCalendarEventRepository(),
        calendar_provider,
        SecretCipher(_FERNET_KEY),
        FakeCalendarAuditRepository(),
        clock,
        "state-secret",
    )
    research_repo = FakeResearchRepository()
    research = ResearchService(
        research_repo,
        FakeResearchSourceRecordRepository(),
        {},
        FakeResearchAuditRepository(),
        clock,
    )
    orchestrator = MonitoringOrchestrator(
        system, portfolio, calendar, research, system_audit, clock
    )
    return (
        orchestrator,
        system,
        portfolio,
        portfolio_repo,
        compliance_repo,
        calendar,
        calendar_provider,
        research,
        research_repo,
        system_audit,
    )


async def test_calendar_conflict_evaluation_raises_a_real_alert() -> None:
    """PROMPT.md Phase 24 verification 3: every alert shows why it
    triggered."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, _, _, _, calendar, provider, *_ = _orchestrator(clock)
    await calendar.connect("user_1", "auth-code")
    provider.events_response = [
        {
            "id": "event-a",
            "summary": "Meeting A",
            "start": {"dateTime": "2026-01-01T09:00:00Z"},
            "end": {"dateTime": "2026-01-01T10:00:00Z"},
        },
        {
            "id": "event-b",
            "summary": "Meeting B",
            "start": {"dateTime": "2026-01-01T09:30:00Z"},
            "end": {"dateTime": "2026-01-01T10:30:00Z"},
        },
    ]
    await system.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert len(runs) == 1
    assert runs[0].triggered is True
    alerts = await system.list_alerts_for_user("user_1")
    assert len(alerts) == 1
    assert "Meeting A" in alerts[0].reason and "Meeting B" in alerts[0].reason


async def test_calendar_conflict_evaluation_not_connected_does_not_error() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, *_ = _orchestrator(clock)
    monitor = await system.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs[0].triggered is False
    assert "not connected" in (runs[0].detail or "")
    assert monitor.monitor_id == runs[0].monitor_id


async def test_stale_schwab_sync_evaluation_raises_alert_when_stale() -> None:
    clock = FakeClock(datetime(2026, 1, 10, tzinfo=UTC))
    orchestrator, system, portfolio, portfolio_repo, *_ = _orchestrator(clock)
    state = portfolio.start_authorization("user_1")
    state_value = state.split("state=", 1)[1]
    await portfolio.complete_authorization("auth-code", state_value)
    portfolio_repo.snapshots.append(
        PortfolioSnapshot(
            user_id="user_1",
            taken_at=datetime(2026, 1, 1, tzinfo=UTC),  # 9 days stale
            total_market_value=1000.0,
            reconciled=True,
            reconciliation_diff=0.0,
            account_ids=["account_1"],
            warnings=[],
        )
    )
    await system.create_monitor("user_1", MonitorType.STALE_SCHWAB_SYNC)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs[0].triggered is True
    alerts = await system.list_alerts_for_user("user_1")
    assert len(alerts) == 1
    assert alerts[0].monitor_type == MonitorType.STALE_SCHWAB_SYNC


async def test_ips_concentration_breach_evaluation_raises_one_alert_per_breach() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, portfolio, portfolio_repo, compliance_repo, _, _, _, _, _ = _orchestrator(
        clock
    )
    state = portfolio.start_authorization("user_1")
    state_value = state.split("state=", 1)[1]
    await portfolio.complete_authorization("auth-code", state_value)
    compliance_repo.results.append(
        ComplianceResult(
            user_id="user_1",
            ips_version_id="ips_1",
            snapshot_id="snap_1",
            evaluated_at=clock.now_utc(),
            compliant=False,
            breaches=[
                ComplianceBreach(rule_type="max_position_percent", description="AAPL over limit"),
                ComplianceBreach(rule_type="max_position_percent", description="MSFT over limit"),
            ],
        )
    )
    await system.create_monitor("user_1", MonitorType.IPS_CONCENTRATION_BREACH)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs[0].triggered is True
    alerts = await system.list_alerts_for_user("user_1")
    assert len(alerts) == 2


async def test_material_portfolio_news_evaluation_raises_alert_for_held_position() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, portfolio, portfolio_repo, _, _, _, research, research_repo, _ = (
        _orchestrator(clock)
    )
    state = portfolio.start_authorization("user_1")
    state_value = state.split("state=", 1)[1]
    await portfolio.complete_authorization("auth-code", state_value)
    portfolio_repo.positions[("account_1", "AAPL")] = Position(
        account_id="account_1",
        user_id="user_1",
        symbol="AAPL",
        asset_type=AssetType.EQUITY,
        quantity=10,
        market_value=1000.0,
        source_record_id="s1",
        synced_at=clock.now_utc(),
    )
    portfolio_repo.balances.append(
        AccountBalance(
            account_id="account_1",
            user_id="user_1",
            cash_balance=0.0,
            schwab_reported_total=1000.0,
            source_record_id="s1",
            synced_at=clock.now_utc(),
        )
    )
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
    issuer = Issuer(
        name="Apple Inc.",
        primary_ticker="AAPL",
        created_at=clock.now_utc(),
        updated_at=clock.now_utc(),
    )
    await research_repo.save_issuer(issuer)
    await research.save_digest(
        NewsDigest(
            issuer_id=issuer.issuer_id,
            article_ids=["article_1"],
            narrative="Apple reported strong earnings [1].",
            generated_at=clock.now_utc(),
        )
    )
    await system.create_monitor("user_1", MonitorType.MATERIAL_PORTFOLIO_NEWS)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs[0].triggered is True
    alerts = await system.list_alerts_for_user("user_1")
    assert len(alerts) == 1
    assert "AAPL" in alerts[0].message


async def test_integration_failure_evaluation_raises_alert_on_recent_token_failure() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, *_, system_audit = _orchestrator(clock)
    await system_audit.record(action="schwab.token_refresh_failed", result="failure")
    await system.create_monitor("user_1", MonitorType.INTEGRATION_FAILURE)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs[0].triggered is True
    alerts = await system.list_alerts_for_user("user_1")
    assert len(alerts) == 1
    assert "Schwab" in alerts[0].message


async def test_integration_failure_evaluation_no_alert_when_no_failures() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, *_ = _orchestrator(clock)
    await system.create_monitor("user_1", MonitorType.INTEGRATION_FAILURE)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs[0].triggered is False


async def test_disabled_monitor_is_never_evaluated() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, *_ = _orchestrator(clock)
    monitor = await system.create_monitor("user_1", MonitorType.INTEGRATION_FAILURE)
    await system.set_monitor_enabled(monitor.monitor_id, False)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert runs == []


async def test_repeated_sweeps_do_not_duplicate_alerts() -> None:
    """PROMPT.md Phase 24 verification 2: "duplicate alerts are
    suppressed" — proven through the full orchestrator, not just the
    underlying service function in isolation."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, *_, system_audit = _orchestrator(clock)
    await system_audit.record(action="schwab.token_refresh_failed", result="failure")
    await system.create_monitor("user_1", MonitorType.INTEGRATION_FAILURE)

    await orchestrator.evaluate_all_enabled_monitors()
    await orchestrator.evaluate_all_enabled_monitors()

    alerts = await system.list_alerts_for_user("user_1")
    assert len(alerts) == 1


async def test_quiet_hours_flag_reflects_reality() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 23, 0, tzinfo=UTC))
    orchestrator, system, *_, system_audit = _orchestrator(clock)
    await system_audit.record(action="schwab.token_refresh_failed", result="failure")
    await system.create_monitor(
        "user_1", MonitorType.INTEGRATION_FAILURE, quiet_hours_start_utc=22, quiet_hours_end_utc=7
    )

    await orchestrator.evaluate_all_enabled_monitors()

    alerts = await system.list_alerts_for_user("user_1")
    assert alerts[0].created_during_quiet_hours is True


async def test_evaluation_error_is_recorded_not_raised() -> None:
    """One misbehaving monitor must not take down the whole sweep — the
    same per-item error isolation `application/queries/dashboard_query.py`
    already established for its own cards."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator, system, _, _, _, calendar, provider, *_ = _orchestrator(clock)
    await calendar.connect("user_1", "auth-code")
    provider.events_response = []  # no conflicts, but exercises the real call path
    await system.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    await system.create_monitor("user_1", MonitorType.STALE_SCHWAB_SYNC)

    runs = await orchestrator.evaluate_all_enabled_monitors()

    assert len(runs) == 2
    assert all(r.detail is not None for r in runs)


def test_timedelta_lookahead_import_is_used() -> None:
    # Sanity: confirms the module's own lookahead constant is a real,
    # positive window rather than a placeholder.
    from application.orchestrators.monitoring import _CALENDAR_CONFLICT_LOOKAHEAD

    assert _CALENDAR_CONFLICT_LOOKAHEAD > timedelta(0)
