"""Uses real Portfolio/Calendar/Approvals/Conversation services backed by
fakes, matching tests/unit/application/orchestrators/test_news_intelligence.py's
own pattern — proves the aggregation wiring against the actual domain
services, not a re-implementation of them.
"""

from datetime import UTC, datetime, timedelta

from application.queries.dashboard_query import DashboardQueryService
from core.config import Settings
from core.time import FakeClock
from domains.approvals.models import RiskLevel
from domains.approvals.service import ApprovalService
from domains.calendar.service import CalendarService
from domains.conversation.service import ConversationService
from domains.portfolio.models import AssetType
from domains.portfolio.schemas import AccountBalance, PortfolioSnapshot, Position
from domains.portfolio.service import PortfolioService
from domains.projects.service import ProjectService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.approvals.fakes import (
    FakeApprovalDecisionRepository,
    FakeApprovalProposalRepository,
)
from tests.unit.domains.approvals.fakes import FakeAuditRepository as FakeApprovalsAuditRepository
from tests.unit.domains.calendar.fakes import FakeAuditRepository as FakeCalendarAuditRepository
from tests.unit.domains.calendar.fakes import (
    FakeCalendarCredentialRepository,
    FakeCalendarEventRepository,
    FakeCalendarProvider,
)
from tests.unit.domains.conversation.fakes import FakeConversationRepository
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
from tests.unit.domains.projects.fakes import FakeAuditRepository as FakeProjectsAuditRepository
from tests.unit.domains.projects.fakes import FakeProjectRepository

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "finnhub_api_key": None,
        "research_contact_email": None,
        "anthropic_api_key": None,
        "ollama_base_url": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _query_service(
    clock: FakeClock,
) -> tuple[
    DashboardQueryService,
    PortfolioService,
    FakePortfolioRepository,
    FakeSchwabCredentialRepository,
    CalendarService,
    FakeCalendarCredentialRepository,
    ApprovalService,
    ConversationService,
    ProjectService,
]:
    portfolio_repo = FakePortfolioRepository()
    schwab_credentials = FakeSchwabCredentialRepository()
    portfolio = PortfolioService(
        schwab_credentials,
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
    )
    calendar_credentials = FakeCalendarCredentialRepository()
    calendar = CalendarService(
        calendar_credentials,
        FakeCalendarEventRepository(),
        FakeCalendarProvider(),
        SecretCipher(_FERNET_KEY),
        FakeCalendarAuditRepository(),
        clock,
        "state-secret",
    )
    approvals = ApprovalService(
        FakeApprovalProposalRepository(),
        FakeApprovalDecisionRepository(),
        FakeApprovalsAuditRepository(),
        clock,
    )
    conversations = ConversationService(FakeConversationRepository(), clock)
    projects = ProjectService(FakeProjectRepository(), FakeProjectsAuditRepository(), clock)
    dashboard = DashboardQueryService(
        portfolio, calendar, approvals, conversations, projects, clock, _settings()
    )
    return (
        dashboard,
        portfolio,
        portfolio_repo,
        schwab_credentials,
        calendar,
        calendar_credentials,
        approvals,
        conversations,
        projects,
    )


async def test_today_card_not_connected_when_no_calendar_credential() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, *_ = _query_service(clock)

    view = await dashboard.build("user_1")

    assert view.today.meta.status == "not_connected"
    assert view.today.events == []


async def test_today_card_ok_when_calendar_connected() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, _, _, _, calendar, _, _, _, _ = _query_service(clock)
    await calendar.connect("user_1", "auth-code-123")

    view = await dashboard.build("user_1")

    assert view.today.meta.status == "ok"
    assert view.today.meta.as_of == clock.now_utc()


async def test_money_card_not_connected_when_no_schwab_credential() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, *_ = _query_service(clock)

    view = await dashboard.build("user_1")

    assert view.money.meta.status == "not_connected"
    assert view.money.dashboard is None


async def test_money_card_no_data_when_connected_but_never_synced() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, portfolio, _, _, _, _, _, _, _ = _query_service(clock)
    state = portfolio.start_authorization("user_1")
    state_value = state.split("state=", 1)[1]
    await portfolio.complete_authorization("auth-code", state_value)

    view = await dashboard.build("user_1")

    assert view.money.meta.status == "no_data"
    assert view.money.dashboard is None


async def test_money_card_ok_with_real_synced_snapshot() -> None:
    """PROMPT.md Phase 22 verification 1: dashboard values come from
    backend APIs — the money card's numbers are the real
    `PortfolioService.get_dashboard` computation, not re-derived here."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, portfolio, portfolio_repo, _, _, _, _, _, _ = _query_service(clock)
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

    view = await dashboard.build("user_1")

    assert view.money.meta.status == "ok"
    assert view.money.dashboard is not None
    assert view.money.dashboard.total_market_value == 1000.0


async def test_approval_inbox_reflects_real_pending_proposal() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, _, _, _, _, _, approvals, _, _ = _query_service(clock)
    proposal = await approvals.propose(
        user_id="user_1",
        action_type="calendar.create_event",
        action_schema_version=1,
        summary="Create a meeting",
        payload={"title": "Standup"},
        target_system="google_calendar",
        expected_effect="a new event is created",
        risk_level=RiskLevel.LOW,
        required_permission="calendar.write",
        ttl=timedelta(hours=1),
    )
    await approvals.submit_for_approval(proposal.proposal_id)

    view = await dashboard.build("user_1")

    assert [p.proposal_id for p in view.approval_inbox.pending] == [proposal.proposal_id]
    assert view.attention.items == [
        item for item in view.attention.items if "awaiting your approval" in item.description
    ]
    assert any("1 action(s) awaiting your approval" in i.description for i in view.attention.items)


async def test_projects_card_no_data_for_new_user() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, *_ = _query_service(clock)

    view = await dashboard.build("user_1")

    assert view.projects.meta.status == "no_data"
    assert view.projects.projects == []


async def test_projects_card_reflects_real_project_task_and_blocker_counts() -> None:
    """PROMPT.md Phase 23 implement item 10: "dashboard summary" —
    verification 1's own "based on stored facts" discipline applies here
    too: the numbers shown are `ProjectService.get_project_status_summary`'s
    real computation, not re-derived in the dashboard layer."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, _, _, _, _, _, _, _, projects = _query_service(clock)
    project = await projects.create_project("user_1", "Kitchen remodel")
    task = await projects.propose_task(project.project_id, "Order cabinets")
    await projects.commit_task(task.task_id)
    await projects.raise_blocker(project.project_id, "Waiting on permit")

    view = await dashboard.build("user_1")

    assert view.projects.meta.status == "ok"
    assert len(view.projects.projects) == 1
    entry = view.projects.projects[0]
    assert entry.name == "Kitchen remodel"
    assert entry.committed_tasks == 1
    assert entry.open_blockers == 1


async def test_projects_card_excludes_archived_projects() -> None:
    from domains.projects.models import ProjectStatus

    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, _, _, _, _, _, _, _, projects = _query_service(clock)
    project = await projects.create_project("user_1", "Old project")
    await projects.update_project_status(project.project_id, ProjectStatus.ARCHIVED)

    view = await dashboard.build("user_1")

    assert view.projects.meta.status == "no_data"
    assert view.projects.projects == []


async def test_conversation_card_reflects_recent_sessions() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, _, _, _, _, _, _, conversations, _ = _query_service(clock)
    session = await conversations.start_session("user_1")

    view = await dashboard.build("user_1")

    assert view.conversation.meta.status == "ok"
    assert [s.session_id for s in view.conversation.recent_sessions] == [session.session_id]


async def test_conversation_card_no_data_for_new_user() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    dashboard, *_ = _query_service(clock)

    view = await dashboard.build("user_1")

    assert view.conversation.meta.status == "no_data"
    assert view.conversation.recent_sessions == []


async def test_integration_status_reflects_real_settings_and_credentials() -> None:
    """PROMPT.md Phase 22 implement item 6: "integration status.\" """
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    portfolio_repo = FakePortfolioRepository()
    schwab_credentials = FakeSchwabCredentialRepository()
    portfolio = PortfolioService(
        schwab_credentials,
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
    )
    calendar = CalendarService(
        FakeCalendarCredentialRepository(),
        FakeCalendarEventRepository(),
        FakeCalendarProvider(),
        SecretCipher(_FERNET_KEY),
        FakeCalendarAuditRepository(),
        clock,
        "state-secret",
    )
    approvals = ApprovalService(
        FakeApprovalProposalRepository(),
        FakeApprovalDecisionRepository(),
        FakeApprovalsAuditRepository(),
        clock,
    )
    conversations = ConversationService(FakeConversationRepository(), clock)
    projects = ProjectService(FakeProjectRepository(), FakeProjectsAuditRepository(), clock)
    dashboard = DashboardQueryService(
        portfolio,
        calendar,
        approvals,
        conversations,
        projects,
        clock,
        _settings(finnhub_api_key="real-key", anthropic_api_key="sk-real"),
    )

    view = await dashboard.build("user_1")

    by_name = {i.name: i.connected for i in view.integration_status.integrations}
    assert by_name["Finnhub"] is True
    assert by_name["Claude"] is True
    assert by_name["Google Calendar"] is False
    assert by_name["Schwab"] is False
    assert by_name["congress-legislators reference data"] is True
