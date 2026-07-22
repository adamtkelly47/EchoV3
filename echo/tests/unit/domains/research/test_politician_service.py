from datetime import UTC, datetime

import pytest

from core.time import FakeClock
from domains.research.errors import PoliticianNotFoundError
from domains.research.service import ResearchService
from tests.unit.domains.research.fakes import (
    FakeAuditRepository,
    FakeLegislatorReferenceProvider,
    FakePtrProvider,
    FakeResearchRepository,
    FakeSourceRecordRepository,
)


def _service(
    clock: FakeClock | None = None,
) -> tuple[
    ResearchService, FakeResearchRepository, FakePtrProvider, FakeLegislatorReferenceProvider
]:
    clock = clock or FakeClock(datetime(2026, 7, 21, tzinfo=UTC))
    repo = FakeResearchRepository()
    ptr = FakePtrProvider()
    legislators = FakeLegislatorReferenceProvider()
    service = ResearchService(
        repo,
        FakeSourceRecordRepository(),
        {},
        FakeAuditRepository(),
        clock,
        None,
        None,
        {"senate_efd": ptr},
        legislators,
    )
    return service, repo, ptr, legislators


def _filing(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "report_kind": "ptr",
        "report_id": "fda235b3",
        "first_name": "Alan",
        "last_name": "Armstrong",
        "office": "Armstrong, Alan (Senator)",
        "filed_at": "07/21/2026",
    }
    defaults.update(overrides)
    return defaults


def _document(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "transactions": [
            {
                "transaction_date": "03/27/2026",
                "owner": "Self",
                "ticker": "UHS",
                "asset_name": "Universal Health Services, Inc. Common Stock",
                "asset_type": "Stock",
                "transaction_type": "Purchase",
                "amount_text": "$1,001 - $15,000",
                "comment": "--",
            }
        ]
    }
    defaults.update(overrides)
    return defaults


def _legislator(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "id": {"bioguide": "A000376"},
        "name": {"first": "Alan", "last": "Armstrong"},
        "terms": [
            {
                "type": "sen",
                "start": "2025-01-03",
                "end": "2031-01-03",
                "state": "WY",
                "party": "Republican",
            }
        ],
    }
    defaults.update(overrides)
    return defaults


async def test_ingest_ptr_transactions_parses_filings_and_resolves_identity() -> None:
    service, _, ptr, legislators = _service()
    ptr.filings = [_filing()]
    ptr.documents_by_report_id["fda235b3"] = _document()
    legislators.legislators = [_legislator()]

    transactions = await service.ingest_ptr_transactions(start_date="2026-01-01")

    assert len(transactions) == 1
    assert transactions[0].politician_bioguide_id == "A000376"
    assert transactions[0].state == "WY"
    assert transactions[0].party == "Republican"
    assert transactions[0].ticker == "UHS"


async def test_ingest_ptr_transactions_skips_paper_filings() -> None:
    """PROMPT.md Phase 19 scope limitation: paper filings have no
    structured table to parse."""
    service, _, ptr, _ = _service()
    ptr.filings = [_filing(report_kind="paper", report_id="paper1")]

    transactions = await service.ingest_ptr_transactions(start_date="2026-01-01")

    assert transactions == []
    assert "paper1" not in ptr.calls


async def test_ingest_ptr_transactions_unresolved_identity_stays_none() -> None:
    """ "Missing stays missing" — no legislators reference data configured
    means every transaction's identity fields resolve to None, never a
    guess."""
    service, _, ptr, _ = _service()
    ptr.filings = [_filing()]
    ptr.documents_by_report_id["fda235b3"] = _document()

    transactions = await service.ingest_ptr_transactions(start_date="2026-01-01")

    assert transactions[0].politician_bioguide_id is None
    assert transactions[0].state is None


async def test_ingest_ptr_transactions_one_filing_failing_does_not_block_the_rest() -> None:
    service, _, ptr, legislators = _service()
    ptr.filings = [_filing(report_id="bad"), _filing(report_id="fda235b3")]
    ptr.documents_by_report_id["fda235b3"] = _document()
    legislators.legislators = [_legislator()]

    transactions = await service.ingest_ptr_transactions(start_date="2026-01-01")

    assert len(transactions) == 1
    assert transactions[0].report_id == "fda235b3"


async def test_reingesting_the_same_filing_does_not_duplicate_stored_transactions() -> None:
    service, _, ptr, legislators = _service()
    ptr.filings = [_filing()]
    ptr.documents_by_report_id["fda235b3"] = _document()
    legislators.legislators = [_legislator()]

    first_pass = await service.ingest_ptr_transactions(start_date="2026-01-01")
    await service.save_politician_transactions(first_pass)
    second_pass = await service.ingest_ptr_transactions(start_date="2026-01-01")
    await service.save_politician_transactions(second_pass)

    stored = await service.list_politician_transactions_for_politician("A000376")
    assert len(stored) == 1


async def test_sync_committee_assignments_saves_and_returns_matching_committees() -> None:
    service, repo, _, legislators = _service()
    legislators.committees = [
        {
            "thomas_id": "SSBK",
            "type": "senate",
            "name": "Senate Committee on Banking, Housing, and Urban Affairs",
            "jurisdiction": "Banking and monetary policy.",
        }
    ]
    legislators.committee_membership = {"SSBK": [{"name": "Alan Armstrong", "bioguide": "A000376"}]}

    assignments = await service.sync_committee_assignments("A000376")

    assert len(assignments) == 1
    assert assignments[0].committee_thomas_id == "SSBK"
    stored = await repo.list_committee_assignments_for_politician("A000376")
    assert len(stored) == 1


async def test_get_politician_evidence_raises_when_nothing_ingested() -> None:
    service, _, _, _ = _service()
    with pytest.raises(PoliticianNotFoundError):
        await service.get_politician_evidence("A000376")


async def test_get_politician_evidence_bundles_profile_and_transactions() -> None:
    service, _, ptr, legislators = _service()
    ptr.filings = [_filing()]
    ptr.documents_by_report_id["fda235b3"] = _document()
    legislators.legislators = [_legislator()]
    transactions = await service.ingest_ptr_transactions(start_date="2026-01-01")
    await service.save_politician_transactions(transactions)

    evidence = await service.get_politician_evidence("A000376")

    assert len(evidence.transactions) == 1
    assert evidence.profile is not None
    assert evidence.profile.transaction_count == 1
    assert evidence.committee_assignments == []  # never synced this run


async def test_get_politician_evidence_computes_committee_relationship_using_synced_issuer() -> (
    None
):
    """PROMPT.md Phase 19 implement item 7/9: sector classification reuses
    this domain's own `sync_issuer`/`get_issuer_by_ticker` (Phase 16) —
    proven end to end here by seeding a real-shaped synced Issuer directly,
    the same reuse `get_politician_evidence`'s own docstring documents."""
    from domains.research.schemas import Issuer

    service, repo, ptr, legislators = _service()
    ptr.filings = [_filing()]
    ptr.documents_by_report_id["fda235b3"] = _document()
    legislators.legislators = [_legislator()]
    legislators.committees = [
        {
            "thomas_id": "SSHR",
            "type": "senate",
            "name": "Senate Committee on Health, Education, Labor, and Pensions",
            "jurisdiction": "Jurisdiction over health and human services programs.",
        }
    ]
    legislators.committee_membership = {"SSHR": [{"name": "Alan Armstrong", "bioguide": "A000376"}]}
    transactions = await service.ingest_ptr_transactions(start_date="2026-01-01")
    await service.save_politician_transactions(transactions)
    await service.sync_committee_assignments("A000376")
    issuer = Issuer(
        name="Universal Health Services",
        primary_ticker="UHS",
        industry="Health Care",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_issuer(issuer)

    evidence = await service.get_politician_evidence("A000376")

    assert len(evidence.committee_assignments) == 1
    committee_features = [
        a for a in evidence.anomalies if a.feature_name == "committee_jurisdiction_overlap"
    ]
    assert len(committee_features) == 1
    assert "Senate Committee on Health, Education, Labor, and Pensions" in (
        committee_features[0].baseline_description
    )
