"""Uses a real ResearchService backed by fakes, matching
tests/unit/application/orchestrators/test_news_intelligence.py's own
pattern — proves the orchestrator's wiring against the actual Phase 18
domain state, not a re-implementation of it.
"""

from datetime import UTC, datetime

from application.orchestrators.insider_intelligence import InsiderIntelligenceOrchestrator
from core.errors import ProviderUnavailableError
from core.time import FakeClock
from domains.research.service import ResearchService
from tests.unit.application.orchestrators.fakes import FakeInsiderModelGateway
from tests.unit.domains.research.fakes import (
    FakeAuditRepository,
    FakeForm4Provider,
    FakeResearchRepository,
    FakeSourceRecordRepository,
)


def _research_service(clock: FakeClock) -> tuple[ResearchService, FakeForm4Provider]:
    form4 = FakeForm4Provider()
    return (
        ResearchService(
            FakeResearchRepository(),
            FakeSourceRecordRepository(),
            {},
            FakeAuditRepository(),
            clock,
            None,
            {"sec_edgar": form4},
        ),
        form4,
    )


def _document(
    *, footnote_ids: list[str] | None = None, footnotes: dict[str, str] | None = None
) -> dict[str, object]:
    return {
        "reporting_owner_cik": "0001234567",
        "reporting_owner_name": "Jane Insider",
        "is_director": False,
        "is_officer": True,
        "is_ten_percent_owner": False,
        "officer_title": "CEO",
        "aff10b5_one": False,
        "transactions": [
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "S",
                "shares": "800",
                "price_per_share": "355.00",
                "acquired_disposed": "D",
                "shares_owned_following": "5000",
                "footnote_ids": footnote_ids or [],
            }
        ],
        "footnotes": footnotes or {},
    }


async def test_ingest_and_classify_uses_no_footnote_directly_without_a_model_call() -> None:
    """Deterministic-when-possible: a transaction with no footnote text
    gets `FilingContext.NO_FOOTNOTE` directly, never a wasted model call."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, form4 = _research_service(clock)
    form4.filings = [{"accession_number": "acc1", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["acc1"] = _document()
    gateway = FakeInsiderModelGateway()
    orchestrator = InsiderIntelligenceOrchestrator(research, gateway)

    transactions = await orchestrator.ingest_and_classify("issuer_1", "0000731766")

    assert transactions[0].filing_context is not None
    assert transactions[0].filing_context.value == "no_footnote"
    assert gateway.structured_calls == []  # no model call for an absent footnote


async def test_ingest_and_classify_classifies_footnote_via_model() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, form4 = _research_service(clock)
    form4.filings = [{"accession_number": "acc1", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["acc1"] = _document(
        footnote_ids=["F1"],
        footnotes={"F1": "This transaction was effected pursuant to a Rule 10b5-1 trading plan."},
    )
    gateway = FakeInsiderModelGateway(filing_context_decisions=["plan_10b5_1_explanation"])
    orchestrator = InsiderIntelligenceOrchestrator(research, gateway)

    transactions = await orchestrator.ingest_and_classify("issuer_1", "0000731766")

    assert transactions[0].filing_context is not None
    assert transactions[0].filing_context.value == "plan_10b5_1_explanation"
    persisted = await research.list_insider_transactions_for_issuer("issuer_1")
    assert persisted[0].filing_context is not None
    assert persisted[0].filing_context.value == "plan_10b5_1_explanation"


async def test_interpret_gives_claude_verified_facts_and_baseline_stated_features() -> None:
    """PROMPT.md Phase 18 verification 5 / CONSTITUTION.md Verified Truth:
    the interpretation prompt separates verified facts from computed
    features and explicitly forbids accusatory language — this test proves
    the guardrail text is actually present in what's sent to the model, not
    just claimed in a docstring."""
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, form4 = _research_service(clock)
    form4.filings = [
        {"accession_number": "acc1", "filing_date": "2026-01-01"},
        {"accession_number": "acc2", "filing_date": "2026-02-01"},
        {"accession_number": "acc3", "filing_date": "2026-03-01"},
    ]
    for accession, (date, shares) in zip(
        ["acc1", "acc2", "acc3"],
        [("2026-01-01", "100"), ("2026-02-01", "100"), ("2026-03-01", "1000")],
        strict=True,
    ):
        doc = _document()
        doc["transactions"][0]["transaction_date"] = date  # type: ignore[index]
        doc["transactions"][0]["shares"] = shares  # type: ignore[index]
        form4.documents_by_accession[accession] = doc
    gateway = FakeInsiderModelGateway(interpretation_output="A neutral, fact-based explanation.")
    orchestrator = InsiderIntelligenceOrchestrator(research, gateway)
    await orchestrator.ingest_and_classify("issuer_1", "0000731766")

    interpretation = await orchestrator.interpret("issuer_1", "0001234567", "UnitedHealth Group")

    assert interpretation == "A neutral, fact-based explanation."
    assert len(gateway.generate_calls) == 1
    prompt = gateway.generate_calls[0].prompt
    assert "VERIFIED FACTS" in prompt
    assert "COMPUTED FEATURES" in prompt
    assert "suspicious" in prompt.lower()  # named explicitly as forbidden
    assert "illegal" in prompt.lower()
    assert "insider trading" in prompt.lower()
    assert "own average transaction size" in prompt  # the real, stated baseline is passed through


async def test_interpret_fails_safe_when_model_unavailable() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    research, form4 = _research_service(clock)
    form4.filings = [{"accession_number": "acc1", "filing_date": "2026-01-15"}]
    form4.documents_by_accession["acc1"] = _document()
    gateway = FakeInsiderModelGateway(raise_on_generate=ProviderUnavailableError("Claude is down"))
    orchestrator = InsiderIntelligenceOrchestrator(research, gateway)
    await orchestrator.ingest_and_classify("issuer_1", "0000731766")

    interpretation = await orchestrator.interpret("issuer_1", "0001234567", "UnitedHealth Group")

    assert "unavailable" in interpretation.lower()
