from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.research.repository import PostgresResearchRepository
from domains.research.schemas import Issuer, ProviderClaim, SecurityMasterEntry


async def test_issuer_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Apple Inc.",
        cik="0000320193",
        primary_ticker="AAPL",
        industry="ELECTRONIC COMPUTERS",
        source_record_ids=["s1", "s2"],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    restored = await repo.get_issuer(issuer.issuer_id)
    assert restored is not None
    assert restored.name == "Apple Inc."
    assert restored.cik == "0000320193"
    assert restored.source_record_ids == ["s1", "s2"]


async def test_issuer_save_upserts_by_issuer_id_and_preserves_conflicts(
    db_session: AsyncSession,
) -> None:
    from domains.research.schemas import FieldConflict

    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Apple Inc",
        primary_ticker="AAPL",
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
        update={"name": "Apple Inc.", "updated_at": datetime(2026, 1, 2, tzinfo=UTC)}
    )
    await repo.save_issuer(updated)

    restored = await repo.get_issuer(issuer.issuer_id)
    assert restored is not None
    assert restored.name == "Apple Inc."
    assert len(restored.conflicts) == 1
    assert restored.conflicts[0].field == "industry"


async def test_get_issuer_by_cik_finds_the_right_row(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Apple Inc.",
        cik="0000320193",
        primary_ticker="AAPL",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    found = await repo.get_issuer_by_cik("0000320193")
    assert found is not None
    assert found.issuer_id == issuer.issuer_id
    assert await repo.get_issuer_by_cik("0000000000") is None


async def test_list_issuers_by_ticker(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    issuer = Issuer(
        name="Apple Inc.",
        primary_ticker="AAPL",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    matches = await repo.list_issuers_by_ticker("AAPL")
    assert len(matches) == 1
    assert matches[0].issuer_id == issuer.issuer_id
    assert await repo.list_issuers_by_ticker("MSFT") == []


async def test_security_save_upserts_by_issuer_and_ticker(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    security = SecurityMasterEntry(
        issuer_id="issuer_1",
        ticker="AAPL",
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
        ticker="AAPL",
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
        ticker="AAPL",
        name="Apple Inc",
        industry="Technology",
        source_record_id="s1",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_claim(claim)

    claims = await repo.list_claims_for_issuer("issuer_1")
    assert len(claims) == 1
    assert claims[0].provider == "finnhub"
    assert claims[0].name == "Apple Inc"


async def test_raw_response_save(db_session: AsyncSession) -> None:
    repo = PostgresResearchRepository(db_session)
    await repo.save_raw_response("raw_1", {"foo": "bar"}, datetime(2026, 1, 1, tzinfo=UTC))
    # No get() on the Protocol — mirrors domains/portfolio's own raw-response
    # test; this exercises the insert path doesn't raise, the real read path
    # is core.provenance's SourceRecord pointing at raw_storage_ref.
