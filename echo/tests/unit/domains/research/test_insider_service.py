from datetime import UTC, datetime

import pytest

from core.time import FakeClock
from domains.research.errors import InsiderNotFoundError
from domains.research.service import ResearchService
from tests.unit.domains.research.fakes import (
    FakeAuditRepository,
    FakeForm4Provider,
    FakeResearchRepository,
    FakeSourceRecordRepository,
)


def _service(
    clock: FakeClock | None = None,
) -> tuple[ResearchService, FakeResearchRepository, FakeForm4Provider]:
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    repo = FakeResearchRepository()
    form4 = FakeForm4Provider()
    service = ResearchService(
        repo,
        FakeSourceRecordRepository(),
        {},
        FakeAuditRepository(),
        clock,
        None,
        {"sec_edgar": form4},
    )
    return service, repo, form4


def _sale_document(
    *, aff10b5_one: bool = False, shares: str = "800", price: str | None = "355.00"
) -> dict[str, object]:
    return {
        "reporting_owner_cik": "0001234567",
        "reporting_owner_name": "Jane Insider",
        "is_director": False,
        "is_officer": True,
        "is_ten_percent_owner": False,
        "officer_title": "CEO",
        "aff10b5_one": aff10b5_one,
        "transactions": [
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "S",
                "shares": shares,
                "price_per_share": price,
                "acquired_disposed": "D",
                "shares_owned_following": "5000",
                "footnote_ids": [],
            }
        ],
        "footnotes": {},
    }


async def test_ingest_form4_transactions_parses_filings_from_the_provider() -> None:
    service, _, form4 = _service()
    form4.filings = [{"accession_number": "0000731766-26-000123", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["0000731766-26-000123"] = _sale_document()

    transactions = await service.ingest_form4_transactions("issuer_1", "0000731766")

    assert len(transactions) == 1
    assert transactions[0].issuer_id == "issuer_1"
    assert transactions[0].insider_cik == "0001234567"
    assert transactions[0].filing_accession_number == "0000731766-26-000123"


async def test_ingest_form4_transactions_one_filing_failing_does_not_block_the_rest() -> None:
    service, _, form4 = _service()
    form4.filings = [
        {"accession_number": "bad-accession", "filing_date": "2026-01-14"},
        {"accession_number": "0000731766-26-000123", "filing_date": "2026-01-15"},
    ]
    # Only the second accession has a document registered — the first
    # raises a KeyError inside the fake, simulating a fetch failure.
    form4.documents_by_accession["0000731766-26-000123"] = _sale_document()

    transactions = await service.ingest_form4_transactions("issuer_1", "0000731766")

    assert len(transactions) == 1
    assert transactions[0].filing_accession_number == "0000731766-26-000123"


async def test_save_and_list_insider_transactions_for_issuer() -> None:
    service, _, form4 = _service()
    form4.filings = [{"accession_number": "acc1", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["acc1"] = _sale_document()
    transactions = await service.ingest_form4_transactions("issuer_1", "0000731766")
    await service.save_insider_transactions(transactions)

    listed = await service.list_insider_transactions_for_issuer("issuer_1")
    assert len(listed) == 1


async def test_reingesting_the_same_filing_does_not_duplicate_stored_transactions() -> None:
    """A scheduled re-sync always re-fetches the most recent N filings —
    re-ingesting an already-seen accession must upsert in place, not
    accumulate duplicate rows that would corrupt profile/anomaly baselines."""
    service, _, form4 = _service()
    form4.filings = [{"accession_number": "acc1", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["acc1"] = _sale_document()

    first_pass = await service.ingest_form4_transactions("issuer_1", "0000731766")
    await service.save_insider_transactions(first_pass)
    second_pass = await service.ingest_form4_transactions("issuer_1", "0000731766")
    await service.save_insider_transactions(second_pass)

    stored = await service.list_insider_transactions_for_issuer("issuer_1")
    assert len(stored) == 1


async def test_get_insider_evidence_raises_when_nothing_ingested() -> None:
    service, _, _ = _service()
    with pytest.raises(InsiderNotFoundError):
        await service.get_insider_evidence("issuer_1", "0001234567")


async def test_get_insider_evidence_computes_anomaly_for_most_recent_transaction() -> None:
    """PROMPT.md Phase 18 implement item 9 / verification 4: the evidence
    view carries deterministic anomaly features with a stated baseline for
    the insider's latest transaction, computed against their own history."""
    service, _, form4 = _service()
    form4.filings = [
        {"accession_number": "acc1", "filing_date": "2026-01-01"},
        {"accession_number": "acc2", "filing_date": "2026-02-01"},
        {"accession_number": "acc3", "filing_date": "2026-03-01"},
    ]
    form4.documents_by_accession["acc1"] = _sale_document(shares="100")
    form4.documents_by_accession["acc1"]["transactions"][0]["transaction_date"] = "2026-01-01"  # type: ignore[index]
    form4.documents_by_accession["acc2"] = _sale_document(shares="100")
    form4.documents_by_accession["acc2"]["transactions"][0]["transaction_date"] = "2026-02-01"  # type: ignore[index]
    form4.documents_by_accession["acc3"] = _sale_document(shares="1000")
    form4.documents_by_accession["acc3"]["transactions"][0]["transaction_date"] = "2026-03-01"  # type: ignore[index]

    transactions = await service.ingest_form4_transactions("issuer_1", "0000731766")
    await service.save_insider_transactions(transactions)

    evidence = await service.get_insider_evidence("issuer_1", "0001234567")

    assert len(evidence.transactions) == 3
    assert evidence.profile is not None
    assert evidence.profile.transaction_count == 3
    size_feature = next(
        a for a in evidence.anomalies if a.feature_name == "transaction_size_vs_personal_baseline"
    )
    assert size_feature.value == 10.0
    assert size_feature.is_notable is True


async def test_get_insider_evidence_planned_sale_only_true_when_aff10b5_one() -> None:
    """PROMPT.md Phase 18 verification 2, exercised through the full
    ingest -> evidence read path (not just the policy function in
    isolation)."""
    service, _, form4 = _service()
    form4.filings = [{"accession_number": "acc1", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["acc1"] = _sale_document(aff10b5_one=True)
    transactions = await service.ingest_form4_transactions("issuer_1", "0000731766")
    await service.save_insider_transactions(transactions)

    evidence = await service.get_insider_evidence("issuer_1", "0001234567")

    assert evidence.transactions[0].is_planned_sale is True
