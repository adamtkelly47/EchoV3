"""PROMPT.md Phase 15's own vocabulary: 13 measured criteria, 8 separate
research needs, evaluated per-provider with live test evidence. This is
deliberately isolated from `domains/` and `providers/` — PROMPT.md Phase 15
is explicit: "Do not select a permanent provider before this phase." Nothing
here is imported by application/domain code; a provider only earns a real
`providers/<name>/adapter.py` once a later phase actually adopts it.

Pure data model, no I/O — matches every other Policy-shaped module in this
codebase (no network calls, no persistence).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Need(str, Enum):
    """PROMPT.md Phase 15's "Evaluate separate needs" list, in the order
    given."""

    FUNDAMENTALS = "fundamentals"
    EARNINGS = "earnings"
    ANALYST_RATINGS = "analyst_ratings"
    COMPANY_NEWS = "company_news"
    SEC_FILINGS = "sec_filings"
    FORM_4_TRANSACTIONS = "form_4_transactions"
    CONGRESSIONAL_DISCLOSURES = "congressional_disclosures"
    MARKET_HISTORY = "market_history"


class Criterion(str, Enum):
    """PROMPT.md Phase 15's 13 measured criteria, in the order given. Not
    every criterion is observable from a single live HTTP call — see
    `Outcome.NOT_LIVE_TESTABLE`."""

    AUTHENTICATION_SUCCESS = "authentication_success"
    ACTUAL_FREE_ACCESS = "actual_free_access"
    RATE_LIMITS_OBSERVED = "rate_limits_observed"
    HISTORICAL_DEPTH = "historical_depth"
    SYMBOL_COVERAGE = "symbol_coverage"
    DATA_FRESHNESS = "data_freshness"
    FIELD_COMPLETENESS = "field_completeness"
    DOCUMENTATION_QUALITY = "documentation_quality"
    RELIABILITY = "reliability"
    LICENSING_CONSTRAINTS = "licensing_constraints"
    RESPONSE_LATENCY = "response_latency"
    SCHEMA_STABILITY = "schema_stability"
    COST_AFTER_FREE_LIMITS = "cost_after_free_limits"


class Outcome(str, Enum):
    """PASS/FAIL/PARTIAL come only from an actual live request that
    succeeded or failed (PROMPT.md Phase 15: "Do not trust a provider's
    statement that a free tier exists unless an actual request succeeds").
    `NOT_EVALUATED` means no credentials were available this pass.
    `NOT_LIVE_TESTABLE` means the criterion is inherently not answerable
    from a single scripted request (e.g. reliability needs sustained
    monitoring over time, licensing constraints are a documentation read,
    not an HTTP response) — recorded honestly rather than assigned a
    fabricated score."""

    # bandit misreads this enum value as a hardcoded password — it's a test
    # outcome label, not a credential.
    PASS = "pass"  # nosec B105
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_EVALUATED = "not_evaluated"
    NOT_LIVE_TESTABLE = "not_live_testable"


@dataclass(frozen=True)
class ProviderTestResult:
    """One (provider, need, criterion) observation. `evidence` is the
    concrete thing actually observed — an HTTP status, a field list, a
    timing figure, a date range — never a paraphrase of marketing copy.

    `need` is `None` for criteria that are properties of the provider as a
    whole rather than any single need (`DOCUMENTATION_QUALITY`,
    `RELIABILITY`, `LICENSING_CONSTRAINTS`, `SCHEMA_STABILITY`,
    `COST_AFTER_FREE_LIMITS` — PROMPT.md's own criteria list doesn't scope
    these per-need, and recording them once per provider instead of once per
    served need avoids duplicating the same qualitative note five times over
    for a provider serving five needs)."""

    provider: str
    need: Need | None
    criterion: Criterion
    outcome: Outcome
    evidence: str
    tested_at: datetime
    notes: str = ""


@dataclass(frozen=True)
class ProviderSummary:
    provider: str
    needs_served: list[Need]
    pass_count: int
    fail_count: int
    partial_count: int
    not_evaluated_count: int
    not_live_testable_count: int


def summarize_provider(provider: str, results: list[ProviderTestResult]) -> ProviderSummary:
    provider_results = [r for r in results if r.provider == provider]
    needs_served = sorted(
        {r.need for r in provider_results if r.need is not None}, key=lambda n: n.value
    )
    counts = {outcome: 0 for outcome in Outcome}
    for r in provider_results:
        counts[r.outcome] += 1
    return ProviderSummary(
        provider=provider,
        needs_served=needs_served,
        pass_count=counts[Outcome.PASS],
        fail_count=counts[Outcome.FAIL],
        partial_count=counts[Outcome.PARTIAL],
        not_evaluated_count=counts[Outcome.NOT_EVALUATED],
        not_live_testable_count=counts[Outcome.NOT_LIVE_TESTABLE],
    )


def group_by_need(results: list[ProviderTestResult]) -> dict[Need, list[ProviderTestResult]]:
    """Provider-level results (`need is None`) are excluded — callers that
    want those should filter `results` for `need is None` directly."""
    grouped: dict[Need, list[ProviderTestResult]] = {}
    for r in results:
        if r.need is not None:
            grouped.setdefault(r.need, []).append(r)
    return grouped
