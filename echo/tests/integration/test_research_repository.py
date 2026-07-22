from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.research.repository import PostgresResearchRepository
from domains.research.schemas import (
    Chamber,
    CommitteeAssignment,
    EventType,
    FilingContext,
    InsiderTransaction,
    Issuer,
    NewsArticle,
    NewsDigest,
    NewsFeedback,
    PoliticianOwner,
    PoliticianTransaction,
    PoliticianTransactionType,
    ProviderClaim,
    SecurityMasterEntry,
    TransactionType,
)


async def test_issuer_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Test Company Inc.",
        cik="9999999999",
        primary_ticker="ZZTEST",
        industry="ELECTRONIC COMPUTERS",
        source_record_ids=["s1", "s2"],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    restored = await repo.get_issuer(issuer.issuer_id)
    assert restored is not None
    assert restored.name == "Test Company Inc."
    assert restored.cik == "9999999999"
    assert restored.source_record_ids == ["s1", "s2"]


async def test_issuer_save_upserts_by_issuer_id_and_preserves_conflicts(
    db_session: AsyncSession,
) -> None:
    from domains.research.schemas import FieldConflict

    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Test Company",
        primary_ticker="ZZTEST",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        conflicts=[
            FieldConflict(
                field="industry",
                values_by_provider={"finnhub": "Technology", "sec_edgar": "ELECTRONIC COMPUTERS"},
                resolved_value="Technology",
                resolved_from_provider="finnhub",
            )
        ],
    )
    await repo.save_issuer(issuer)

    updated = issuer.model_copy(
        update={"name": "Test Company Inc.", "updated_at": datetime(2026, 1, 2, tzinfo=UTC)}
    )
    await repo.save_issuer(updated)

    restored = await repo.get_issuer(issuer.issuer_id)
    assert restored is not None
    assert restored.name == "Test Company Inc."
    assert len(restored.conflicts) == 1
    assert restored.conflicts[0].field == "industry"


async def test_get_issuer_by_cik_finds_the_right_row(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Test Company Inc.",
        cik="9999999999",
        primary_ticker="ZZTEST",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    found = await repo.get_issuer_by_cik("9999999999")
    assert found is not None
    assert found.issuer_id == issuer.issuer_id
    assert await repo.get_issuer_by_cik("0000000000") is None


async def test_list_issuers_by_ticker(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Test Company Inc.",
        primary_ticker="ZZTEST",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    matches = await repo.list_issuers_by_ticker("ZZTEST")
    assert len(matches) == 1
    assert matches[0].issuer_id == issuer.issuer_id
    assert await repo.list_issuers_by_ticker("MSFT") == []


async def test_security_save_upserts_by_issuer_and_ticker(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    security = SecurityMasterEntry(
        issuer_id="issuer_1",
        ticker="ZZTEST",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    first_saved = await repo.save_security(security)

    # A fresh SecurityMasterEntry (new random security_id) for the same
    # (issuer_id, ticker) must reuse the existing row's stable id — the
    # same upsert-preserving-id contract as domains/portfolio/repository.py's
    # save_account (Docs/DECISION_LOG.md's Phase 12 entry).
    fresh = SecurityMasterEntry(
        issuer_id="issuer_1",
        ticker="ZZTEST",
        exchange="NASDAQ",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    second_saved = await repo.save_security(fresh)

    assert second_saved.security_id == first_saved.security_id
    securities = await repo.list_securities_for_issuer("issuer_1")
    assert len(securities) == 1
    assert securities[0].exchange == "NASDAQ"


async def test_claim_save_and_list_for_issuer(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    claim = ProviderClaim(
        issuer_id="issuer_1",
        provider="finnhub",
        ticker="ZZTEST",
        name="Test Company",
        industry="Technology",
        source_record_id="s1",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_claim(claim)

    claims = await repo.list_claims_for_issuer("issuer_1")
    assert len(claims) == 1
    assert claims[0].provider == "finnhub"
    assert claims[0].name == "Test Company"


async def test_raw_response_save(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    await repo.save_raw_response("raw_1", {"foo": "bar"}, datetime(2026, 1, 1, tzinfo=UTC))
    # No get() on the Protocol — mirrors domains/portfolio's own raw-response
    # test; this exercises the insert path doesn't raise, the real read path
    # is core.provenance's SourceRecord pointing at raw_storage_ref.


async def test_article_save_upserts_by_article_id_and_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    article = NewsArticle(
        issuer_id="issuer_1",
        headline="Company beats Q3 earnings estimates",
        blurb="A short blurb.",
        source="Reuters",
        url="https://example.com/1",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_record_id="s1",
        cluster_id="c1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_articles([article])

    enriched = article.model_copy(
        update={
            "event_type": EventType.EARNINGS,
            "summary": "The company beat Q3 earnings estimates.",
            "relevance_score": 0.85,
        }
    )
    await repo.save_articles([enriched])

    articles = await repo.list_articles_for_issuer("issuer_1")
    assert len(articles) == 1  # upserted, not duplicated
    assert articles[0].event_type == EventType.EARNINGS
    assert articles[0].summary == "The company beat Q3 earnings estimates."
    assert articles[0].relevance_score == 0.85
    assert articles[0].blurb == "A short blurb."


async def test_digest_save_and_get_latest(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    first = NewsDigest(
        issuer_id="issuer_1",
        article_ids=["article_1"],
        narrative="First narrative [1].",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = NewsDigest(
        issuer_id="issuer_1",
        article_ids=["article_1", "article_2"],
        narrative="Second narrative [1][2].",
        generated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await repo.save_digest(first)
    await repo.save_digest(second)

    latest = await repo.get_latest_digest("issuer_1")
    assert latest is not None
    assert latest.narrative == "Second narrative [1][2]."
    assert latest.article_ids == ["article_1", "article_2"]
    assert await repo.get_latest_digest("never_synced_issuer") is None


async def test_feedback_save_and_list_for_article(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    feedback = NewsFeedback(
        article_id="article_1",
        user_id="live_user",
        useful=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_feedback(feedback)

    stored = await repo.list_feedback_for_article("article_1")
    assert len(stored) == 1
    assert stored[0].useful is True
    assert stored[0].user_id == "live_user"


def _insider_transaction(**overrides: object) -> InsiderTransaction:
    defaults: dict[str, object] = {
        "issuer_id": "issuer_1",
        "insider_cik": "0001234567",
        "insider_name": "Jane Insider",
        "is_director": False,
        "is_officer": True,
        "is_ten_percent_owner": False,
        "officer_title": "CEO",
        "transaction_date": datetime(2026, 1, 15, tzinfo=UTC),
        "transaction_code": "S",
        "transaction_type": TransactionType.OPEN_MARKET_SALE,
        "shares": 800.0,
        "price_per_share": 355.0,
        "transaction_value": 284000.0,
        "acquired_disposed": "D",
        "shares_owned_after": 5000.0,
        "ownership_change_percent": 13.79,
        "is_planned_sale": False,
        "footnote_text": None,
        "filing_context": None,
        "filing_accession_number": "0000731766-26-000123",
        "source_record_id": "s1",
        "synced_at": datetime(2026, 1, 20, tzinfo=UTC),
    }
    defaults.update(overrides)
    return InsiderTransaction(**defaults)  # type: ignore[arg-type]


async def test_insider_transaction_save_and_round_trip(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    transaction = _insider_transaction()
    await repo.save_insider_transactions([transaction])

    restored = await repo.list_insider_transactions_for_issuer("issuer_1")
    assert len(restored) == 1
    assert restored[0].transaction_id == transaction.transaction_id
    assert restored[0].insider_cik == "0001234567"
    assert restored[0].transaction_type == TransactionType.OPEN_MARKET_SALE
    assert restored[0].transaction_value == 284000.0
    assert restored[0].is_planned_sale is False
    assert restored[0].filing_context is None


async def test_insider_transaction_save_upserts_by_transaction_id_to_enrich_filing_context(
    db_session: AsyncSession,
) -> None:
    """Mirrors `save_articles`'s enrich-in-place upsert: the deterministic
    ingest saves a transaction without `filing_context`, then a later save
    (after Ollama classification) fills it in without creating a duplicate
    row."""
    repo = PostgresResearchRepository(db_session)
    transaction = _insider_transaction()
    await repo.save_insider_transactions([transaction])

    enriched = transaction.model_copy(update={"filing_context": FilingContext.ROUTINE_COMPENSATION})
    await repo.save_insider_transactions([enriched])

    restored = await repo.list_insider_transactions_for_issuer("issuer_1")
    assert len(restored) == 1  # upserted, not duplicated
    assert restored[0].filing_context == FilingContext.ROUTINE_COMPENSATION


async def test_list_insider_transactions_for_insider_scopes_by_issuer_and_cik(
    db_session: AsyncSession,
) -> None:
    repo = PostgresResearchRepository(db_session)
    target = _insider_transaction(issuer_id="issuer_1", insider_cik="0001234567")
    other_insider = _insider_transaction(issuer_id="issuer_1", insider_cik="0009999999")
    other_issuer = _insider_transaction(issuer_id="issuer_2", insider_cik="0001234567")
    await repo.save_insider_transactions([target, other_insider, other_issuer])

    matches = await repo.list_insider_transactions_for_insider("issuer_1", "0001234567")
    assert len(matches) == 1
    assert matches[0].transaction_id == target.transaction_id


def _politician_transaction(**overrides: object) -> PoliticianTransaction:
    defaults: dict[str, object] = {
        "politician_bioguide_id": "A000376",
        "politician_name": "Alan Armstrong",
        "chamber": Chamber.SENATE,
        "state": "WY",
        "party": "Republican",
        "report_id": "fda235b3-bad7-4637-8fa1-053f354d929c",
        "filed_at": datetime(2026, 7, 21, tzinfo=UTC),
        "transaction_date": datetime(2026, 3, 27, tzinfo=UTC),
        "owner": PoliticianOwner.SELF,
        "ticker": "UHS",
        "asset_name": "Universal Health Services, Inc. Common Stock",
        "asset_type": "Stock",
        "transaction_type": PoliticianTransactionType.PURCHASE,
        "range_low": 1001.0,
        "range_high": 15000.0,
        "filing_delay_days": 116,
        "comment": None,
        "source_record_id": "s1",
        "synced_at": datetime(2026, 7, 21, tzinfo=UTC),
    }
    defaults.update(overrides)
    return PoliticianTransaction(**defaults)  # type: ignore[arg-type]


async def test_politician_transaction_save_and_round_trip(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    transaction = _politician_transaction()
    await repo.save_politician_transactions([transaction])

    restored = await repo.list_politician_transactions_for_politician("A000376")
    assert len(restored) == 1
    assert restored[0].transaction_id == transaction.transaction_id
    assert restored[0].chamber == Chamber.SENATE
    assert restored[0].owner == PoliticianOwner.SELF
    assert restored[0].transaction_type == PoliticianTransactionType.PURCHASE
    assert restored[0].range_low == 1001.0
    assert restored[0].range_high == 15000.0


async def test_politician_transaction_open_ended_range_round_trips_as_none(
    db_session: AsyncSession,
) -> None:
    """PROMPT.md Phase 19 verification 1: an open-ended "Over $X"
    disclosure's `range_high` stays `None` through a real round trip, never
    coerced into a fabricated ceiling."""
    repo = PostgresResearchRepository(db_session)
    transaction = _politician_transaction(range_low=50000000.0, range_high=None)
    await repo.save_politician_transactions([transaction])

    restored = await repo.list_politician_transactions_for_politician("A000376")
    assert restored[0].range_high is None


async def test_politician_transaction_save_upserts_by_transaction_id(
    db_session: AsyncSession,
) -> None:
    """Mirrors the insider-transaction upsert test: re-saving the same
    transaction_id (a real re-sync re-fetching the same report) updates the
    row in place rather than duplicating it."""
    repo = PostgresResearchRepository(db_session)
    transaction = _politician_transaction()
    await repo.save_politician_transactions([transaction])

    enriched = transaction.model_copy(update={"party": "Independent"})
    await repo.save_politician_transactions([enriched])

    restored = await repo.list_politician_transactions_for_politician("A000376")
    assert len(restored) == 1  # upserted, not duplicated
    assert restored[0].party == "Independent"


async def test_list_politician_transactions_for_ticker_scopes_correctly(
    db_session: AsyncSession,
) -> None:
    repo = PostgresResearchRepository(db_session)
    target = _politician_transaction(ticker="UHS")
    other_ticker = _politician_transaction(
        politician_bioguide_id="B000000", ticker="AAPL", report_id="other-report"
    )
    await repo.save_politician_transactions([target, other_ticker])

    matches = await repo.list_politician_transactions_for_ticker("UHS")
    assert len(matches) == 1
    assert matches[0].transaction_id == target.transaction_id


def _committee_assignment(**overrides: object) -> CommitteeAssignment:
    defaults: dict[str, object] = {
        "politician_bioguide_id": "A000376",
        "committee_thomas_id": "SSBK",
        "committee_name": "Senate Committee on Banking, Housing, and Urban Affairs",
        "chamber": Chamber.SENATE,
        "jurisdiction_text": "Banking and monetary policy.",
        "source_record_id": "s1",
        "synced_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return CommitteeAssignment(**defaults)  # type: ignore[arg-type]


async def test_committee_assignment_save_and_round_trip(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    assignment = _committee_assignment()
    await repo.save_committee_assignments([assignment])

    restored = await repo.list_committee_assignments_for_politician("A000376")
    assert len(restored) == 1
    assert restored[0].committee_thomas_id == "SSBK"
    assert restored[0].jurisdiction_text == "Banking and monetary policy."


async def test_committee_assignment_save_upserts_by_composite_key(
    db_session: AsyncSession,
) -> None:
    """A re-synced snapshot overwrites the same (politician, committee)
    row in place rather than accumulating stale duplicates."""
    repo = PostgresResearchRepository(db_session)
    assignment = _committee_assignment()
    await repo.save_committee_assignments([assignment])

    updated = assignment.model_copy(update={"jurisdiction_text": "Updated jurisdiction text."})
    await repo.save_committee_assignments([updated])

    restored = await repo.list_committee_assignments_for_politician("A000376")
    assert len(restored) == 1
    assert restored[0].jurisdiction_text == "Updated jurisdiction text."
