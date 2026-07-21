from datetime import UTC, datetime

from scripts.provider_evaluation.metrics import (
    Criterion,
    Need,
    Outcome,
    ProviderTestResult,
    group_by_need,
    summarize_provider,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_summarize_provider_counts_outcomes_and_needs_served() -> None:
    results = [
        ProviderTestResult(
            "acme", Need.FUNDAMENTALS, Criterion.AUTHENTICATION_SUCCESS, Outcome.PASS, "ok", _NOW
        ),
        ProviderTestResult(
            "acme", Need.FUNDAMENTALS, Criterion.ACTUAL_FREE_ACCESS, Outcome.FAIL, "paywalled", _NOW
        ),
        ProviderTestResult(
            "acme",
            Need.EARNINGS,
            Criterion.AUTHENTICATION_SUCCESS,
            Outcome.PARTIAL,
            "rate limited",
            _NOW,
        ),
        ProviderTestResult(
            "acme", None, Criterion.DOCUMENTATION_QUALITY, Outcome.NOT_LIVE_TESTABLE, "n/a", _NOW
        ),
        ProviderTestResult(
            "other",
            Need.FUNDAMENTALS,
            Criterion.AUTHENTICATION_SUCCESS,
            Outcome.NOT_EVALUATED,
            "no key",
            _NOW,
        ),
    ]

    summary = summarize_provider("acme", results)

    assert summary.needs_served == [Need.EARNINGS, Need.FUNDAMENTALS]
    assert summary.pass_count == 1
    assert summary.fail_count == 1
    assert summary.partial_count == 1
    assert summary.not_live_testable_count == 1
    assert summary.not_evaluated_count == 0  # that one belongs to "other"


def test_group_by_need_excludes_provider_level_results() -> None:
    results = [
        ProviderTestResult(
            "acme", Need.FUNDAMENTALS, Criterion.AUTHENTICATION_SUCCESS, Outcome.PASS, "ok", _NOW
        ),
        ProviderTestResult(
            "acme", None, Criterion.DOCUMENTATION_QUALITY, Outcome.NOT_LIVE_TESTABLE, "n/a", _NOW
        ),
    ]

    grouped = group_by_need(results)

    assert list(grouped.keys()) == [Need.FUNDAMENTALS]
    assert len(grouped[Need.FUNDAMENTALS]) == 1
