from datetime import UTC, datetime

import pytest

from core.errors import ProviderUnavailableError
from core.time import FakeClock
from domains.research.errors import (
    IssuerNotFoundError,
    NoDigestAvailableError,
    NoProviderDataAvailableError,
)
from domains.research.service import ResearchService
from tests.unit.domains.research.fakes import (
    FakeAuditRepository,
    FakeFinnhubProvider,
    FakeResearchRepository,
    FakeSecEdgarProvider,
    FakeSourceRecordRepository,
)


def _service(
    clock: FakeClock | None = None,
) -> tuple[ResearchService, FakeResearchRepository, FakeFinnhubProvider, FakeSecEdgarProvider]:
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    repo = FakeResearchRepository()
    finnhub = FakeFinnhubProvider()
    sec_edgar = FakeSecEdgarProvider()
    service = ResearchService(
        repo,
        FakeSourceRecordRepository(),
        {"finnhub": finnhub, "sec_edgar": sec_edgar},
        FakeAuditRepository(),
        clock,
        {"finnhub": finnhub},
    )
    return service, repo, finnhub, sec_edgar


async def test_sync_issuer_from_two_providers_maps_into_the_same_issuer() -> None:
    """PROMPT.md Phase 16 verification 1: two providers can map into the
    same domain schema."""
    service, repo, finnhub, sec_edgar = _service()
    finnhub.response = {
        "name": "Apple Inc",
        "ticker": "AAPL",
        "finnhubIndustry": "Technology",
    }
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }

    issuer = await service.sync_issuer("AAPL")

    claims = await repo.list_claims_for_issuer(issuer.issuer_id)
    assert {c.provider for c in claims} == {"finnhub", "sec_edgar"}
    assert issuer.cik == "0000320193"
    assert issuer.primary_ticker == "AAPL"


async def test_sync_issuer_surfaces_a_real_provider_disagreement() -> None:
    """PROMPT.md Phase 16 verification 2: source conflicts remain visible."""
    service, _, finnhub, sec_edgar = _service()
    finnhub.response = {"name": "Apple Inc", "ticker": "AAPL", "finnhubIndustry": "Technology"}
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }

    issuer = await service.sync_issuer("AAPL")

    industry_conflict = next(c for c in issuer.conflicts if c.field == "industry")
    assert industry_conflict.values_by_provider == {
        "finnhub": "Technology",
        "sec_edgar": "ELECTRONIC COMPUTERS",
    }


async def test_sync_issuer_entity_resolution_matches_by_cik_regardless_of_ingestion_order() -> None:
    """A ticker-only claim (Finnhub) ingested first must still merge into
    the same issuer a CIK-bearing claim (SEC EDGAR) resolves to — entity
    resolution isn't sensitive to which provider happened to respond, or be
    configured, first (PROMPT.md Phase 16 implement item 7)."""
    service, repo, finnhub, sec_edgar = _service()
    finnhub.response = {"name": "Apple Inc", "ticker": "AAPL", "finnhubIndustry": "Technology"}
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }
    first = await service.sync_issuer("AAPL")

    # Re-sync — must reuse the same issuer, not create a duplicate.
    second = await service.sync_issuer("AAPL")

    assert first.issuer_id == second.issuer_id
    assert len(repo.issuers) == 1


async def test_sync_issuer_one_provider_failing_does_not_block_the_others() -> None:
    """PROMPT.md Phase 16 implement item 10: provider fallback rules."""
    service, _, finnhub, sec_edgar = _service()
    finnhub.raise_error = ProviderUnavailableError("Finnhub is down")
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }

    issuer = await service.sync_issuer("AAPL")

    assert issuer.cik == "0000320193"
    assert issuer.name == "Apple Inc."


async def test_sync_issuer_raises_when_every_provider_fails() -> None:
    service, _, finnhub, sec_edgar = _service()
    finnhub.raise_error = ProviderUnavailableError("down")
    sec_edgar.raise_error = ProviderUnavailableError("down")

    with pytest.raises(NoProviderDataAvailableError):
        await service.sync_issuer("AAPL")


async def test_sync_issuer_retains_source_lineage() -> None:
    """PROMPT.md Phase 16 verification 4: every normalized item retains
    source lineage."""
    service, _, finnhub, sec_edgar = _service()
    finnhub.response = {"name": "Apple Inc", "ticker": "AAPL", "finnhubIndustry": "Technology"}
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }

    issuer = await service.sync_issuer("AAPL")

    assert len(issuer.source_record_ids) == 2


async def test_get_evidence_package_bundles_issuer_securities_and_claims() -> None:
    service, _, finnhub, sec_edgar = _service()
    finnhub.response = {"name": "Apple Inc", "ticker": "AAPL", "finnhubIndustry": "Technology"}
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }
    issuer = await service.sync_issuer("AAPL")

    package = await service.get_evidence_package(issuer.issuer_id)

    assert package.issuer.issuer_id == issuer.issuer_id
    assert len(package.securities) == 1
    assert package.securities[0].ticker == "AAPL"
    assert len(package.claims) == 2
    assert package.is_stale is False


async def test_get_evidence_package_missing_issuer_raises() -> None:
    service, _, _, _ = _service()
    with pytest.raises(IssuerNotFoundError):
        await service.get_evidence_package("never_synced")


async def test_get_evidence_package_flags_stale_data() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service, _, finnhub, sec_edgar = _service(clock=clock)
    finnhub.response = {"name": "Apple Inc", "ticker": "AAPL", "finnhubIndustry": "Technology"}
    sec_edgar.response = {
        "name": "Apple Inc.",
        "cik": 320193,
        "sicDescription": "ELECTRONIC COMPUTERS",
    }
    issuer = await service.sync_issuer("AAPL")

    clock.set(datetime(2026, 3, 1, tzinfo=UTC))  # more than 30 days later
    package = await service.get_evidence_package(issuer.issuer_id)

    assert package.is_stale is True


async def test_get_issuer_by_ticker_returns_none_when_never_synced() -> None:
    service, _, _, _ = _service()
    assert await service.get_issuer_by_ticker("AAPL") is None


async def test_ingest_news_parses_articles_from_configured_news_providers() -> None:
    service, _, finnhub, _ = _service()
    finnhub.news_response = [
        {
            "headline": "Company beats earnings estimates",
            "summary": "A short blurb.",
            "source": "Reuters",
            "url": "https://example.com/1",
            "datetime": 1767225600,
        }
    ]

    articles = await service.ingest_news("issuer_1", "AAPL")

    assert len(articles) == 1
    assert articles[0].issuer_id == "issuer_1"
    assert articles[0].headline == "Company beats earnings estimates"


async def test_ingest_news_one_provider_failing_returns_empty_not_a_crash() -> None:
    service, _, finnhub, _ = _service()
    finnhub.raise_error = ProviderUnavailableError("Finnhub is down")

    articles = await service.ingest_news("issuer_1", "AAPL")

    assert articles == []


async def test_save_and_list_articles_for_issuer() -> None:
    from domains.research.schemas import NewsArticle

    service, _, _, _ = _service()
    article = NewsArticle(
        issuer_id="issuer_1",
        headline="Headline",
        source="Reuters",
        url="https://example.com/1",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_record_id="s1",
        cluster_id="c1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await service.save_articles([article])

    articles = await service.list_articles_for_issuer("issuer_1")
    assert len(articles) == 1
    assert articles[0].headline == "Headline"


async def test_get_latest_digest_without_one_raises() -> None:
    service, _, _, _ = _service()
    with pytest.raises(NoDigestAvailableError):
        await service.get_latest_digest("issuer_1")


async def test_save_and_get_latest_digest() -> None:
    from domains.research.schemas import NewsDigest

    service, _, _, _ = _service()
    digest = NewsDigest(
        issuer_id="issuer_1",
        article_ids=["article_1"],
        narrative="A synthesized narrative [1].",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await service.save_digest(digest)

    latest = await service.get_latest_digest("issuer_1")
    assert latest.narrative == "A synthesized narrative [1]."


async def test_record_feedback_persists_and_audits() -> None:
    service, repo, _, _ = _service()
    feedback = await service.record_feedback("article_1", "live_user", True)

    assert feedback.article_id == "article_1"
    assert feedback.useful is True
    stored = await repo.list_feedback_for_article("article_1")
    assert len(stored) == 1
