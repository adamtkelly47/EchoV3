"""Uses a real ResearchService and a real PortfolioService, both backed by
fakes (matching tests/unit/application/orchestrators/test_calendar_writes.py's
own pattern) — proves the orchestrator's wiring against the actual Phase 12
and Phase 16 domain state, not a re-implementation of it.
"""

from datetime import UTC, datetime

from application.orchestrators.news_intelligence import NewsIntelligenceOrchestrator
from core.time import FakeClock
from domains.portfolio.models import AssetType
from domains.portfolio.schemas import AccountBalance, PortfolioSnapshot, Position
from domains.portfolio.service import PortfolioService
from domains.research.service import ResearchService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.application.orchestrators.fakes import FakeNewsModelGateway
from tests.unit.domains.portfolio.fakes import (
    FakeAuditRepository as FakePortfolioAuditRepository,
)
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
from tests.unit.domains.research.fakes import (
    FakeAuditRepository as FakeResearchAuditRepository,
)
from tests.unit.domains.research.fakes import (
    FakeFinnhubProvider,
    FakeResearchRepository,
    FakeSecEdgarProvider,
)
from tests.unit.domains.research.fakes import (
    FakeSourceRecordRepository as FakeResearchSourceRecordRepository,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _research_service(clock: FakeClock) -> tuple[ResearchService, FakeFinnhubProvider]:
    finnhub = FakeFinnhubProvider()
    return (
        ResearchService(
            FakeResearchRepository(),
            FakeResearchSourceRecordRepository(),
            {"finnhub": finnhub, "sec_edgar": FakeSecEdgarProvider()},
            FakeResearchAuditRepository(),
            clock,
            {"finnhub": finnhub},
        ),
        finnhub,
    )


def _portfolio_service(clock: FakeClock) -> tuple[PortfolioService, FakePortfolioRepository]:
    portfolio_repo = FakePortfolioRepository()
    service = PortfolioService(
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
    )
    return service, portfolio_repo


async def _seed_portfolio_holding(
    portfolio_repo: FakePortfolioRepository, *, user_id: str, symbol: str, now: datetime
) -> None:
    """Directly populates the fake repository with a synced snapshot
    holding `symbol` — bypasses the full Schwab OAuth/sync dance (already
    covered by tests/unit/domains/portfolio/test_portfolio_service.py),
    since this test only needs a realistic PortfolioService.get_dashboard()
    answer, not to re-prove Phase 12's own sync pipeline."""
    portfolio_repo.positions[("account_1", symbol)] = Position(
        account_id="account_1",
        user_id=user_id,
        symbol=symbol,
        asset_type=AssetType.EQUITY,
        quantity=10,
        market_value=1000.0,
        source_record_id="s1",
        synced_at=now,
    )
    portfolio_repo.balances.append(
        AccountBalance(
            account_id="account_1",
            user_id=user_id,
            cash_balance=0.0,
            schwab_reported_total=1000.0,
            source_record_id="s1",
            synced_at=now,
        )
    )
    portfolio_repo.snapshots.append(
        PortfolioSnapshot(
            user_id=user_id,
            taken_at=now,
            total_market_value=1000.0,
            reconciled=True,
            reconciliation_diff=0.0,
            account_ids=["account_1"],
            warnings=[],
        )
    )


def _finnhub_news_item(headline: str, *, source: str = "Reuters") -> dict[str, object]:
    return {
        "headline": headline,
        "summary": f"Blurb for: {headline}",
        "source": source,
        "url": f"https://example.com/{hash(headline)}",
        "datetime": 1767225600,
    }


async def test_run_digest_produces_a_narrative_citing_the_articles() -> None:
    """PROMPT.md Phase 17 verification 4: the final narrative links back to
    evidence."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, finnhub = _research_service(clock)
    portfolio, _ = _portfolio_service(clock)
    finnhub.news_response = [_finnhub_news_item("Company beats Q3 earnings estimates")]
    gateway = FakeNewsModelGateway(
        event_type_decisions=["earnings"],
        summary_decisions=["The company beat Q3 earnings estimates."],
        synthesis_output="The company reported strong earnings [1].",
    )
    orchestrator = NewsIntelligenceOrchestrator(research, portfolio, gateway, clock)

    digest = await orchestrator.run_digest("issuer_1", "AAPL", "Apple Inc.", "live_user")

    assert digest.narrative == "The company reported strong earnings [1]."
    assert len(digest.article_ids) == 1
    articles = await research.list_articles_for_issuer("issuer_1")
    assert articles[0].event_type.value == "earnings"
    assert articles[0].summary == "The company beat Q3 earnings estimates."


async def test_run_digest_with_no_articles_skips_synthesis_call() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, finnhub = _research_service(clock)
    portfolio, _ = _portfolio_service(clock)
    finnhub.news_response = []
    gateway = FakeNewsModelGateway()
    orchestrator = NewsIntelligenceOrchestrator(research, portfolio, gateway, clock)

    digest = await orchestrator.run_digest("issuer_1", "AAPL", "Apple Inc.", "live_user")

    assert "No materially relevant news" in digest.narrative
    assert gateway.generate_calls == []  # never called Claude for an empty story set


async def test_run_digest_boosts_a_real_portfolio_holding_above_a_non_holding() -> None:
    """PROMPT.md Phase 17 verification 3: material portfolio news outranks
    generic popularity — proven end to end through the orchestrator, not
    just the underlying policy function."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, finnhub = _research_service(clock)
    portfolio, portfolio_repo = _portfolio_service(clock)
    await _seed_portfolio_holding(
        portfolio_repo, user_id="live_user", symbol="AAPL", now=clock.now_utc()
    )
    # A held ticker's routine product news vs. an unrelated non-held
    # ticker's routine product news — the *only* difference is the holding.
    finnhub.news_response = [_finnhub_news_item("New product unveiled at event")]
    gateway = FakeNewsModelGateway(
        event_type_decisions=["product"], summary_decisions=["A new product was unveiled."]
    )
    orchestrator = NewsIntelligenceOrchestrator(research, portfolio, gateway, clock)

    held_digest = await orchestrator.run_digest("issuer_1", "AAPL", "Apple Inc.", "live_user")
    held_articles = await research.list_articles_for_issuer("issuer_1")

    # Re-run for a ticker that is *not* held, same event type, same source.
    finnhub.news_response = [_finnhub_news_item("New product unveiled at event")]
    gateway2 = FakeNewsModelGateway(
        event_type_decisions=["product"], summary_decisions=["A new product was unveiled."]
    )
    orchestrator2 = NewsIntelligenceOrchestrator(research, portfolio, gateway2, clock)
    await orchestrator2.run_digest("issuer_2", "ZZZZ", "Not Held Inc.", "live_user")
    not_held_articles = await research.list_articles_for_issuer("issuer_2")

    assert held_digest.article_ids  # the holding produced a real digest
    assert (held_articles[0].relevance_score or 0) > (not_held_articles[0].relevance_score or 0)


async def test_run_digest_persists_non_top_articles_too() -> None:
    """Only the digest is small (PROMPT.md's own objective) — every scored
    article, including ones that didn't make the final cut, is still
    persisted (verifiable, not silently discarded)."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, finnhub = _research_service(clock)
    portfolio, _ = _portfolio_service(clock)
    finnhub.news_response = [
        _finnhub_news_item("Company beats Q3 earnings estimates", source="Reuters"),
        _finnhub_news_item("Some unrelated minor blog post", source="Some Random Blog"),
    ]
    gateway = FakeNewsModelGateway(
        event_type_decisions=["earnings", "other"],
        summary_decisions=["The company beat Q3 earnings estimates."],
    )
    orchestrator = NewsIntelligenceOrchestrator(research, portfolio, gateway, clock)

    digest = await orchestrator.run_digest("issuer_1", "AAPL", "Apple Inc.", "live_user", top_n=1)

    all_articles = await research.list_articles_for_issuer("issuer_1")
    assert len(all_articles) == 2  # both persisted
    assert len(digest.article_ids) == 1  # only the top one surfaced in the digest
