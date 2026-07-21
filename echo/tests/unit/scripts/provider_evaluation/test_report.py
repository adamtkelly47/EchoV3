from datetime import UTC, datetime

from scripts.provider_evaluation.metrics import Criterion, Need, Outcome, ProviderTestResult
from scripts.provider_evaluation.report import render_report

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_render_report_includes_provider_and_need_sections() -> None:
    results = [
        ProviderTestResult(
            "acme",
            Need.FUNDAMENTALS,
            Criterion.AUTHENTICATION_SUCCESS,
            Outcome.PASS,
            "HTTP 200",
            _NOW,
        ),
        ProviderTestResult(
            "acme",
            None,
            Criterion.DOCUMENTATION_QUALITY,
            Outcome.NOT_LIVE_TESTABLE,
            "assessed from docs",
            _NOW,
            notes="not live API evidence",
        ),
    ]

    report = render_report(results, _NOW)

    assert "## acme" in report
    assert "### acme — fundamentals" in report
    assert "### acme — provider-level criteria" in report
    assert "authentication_success" in report
    assert "documentation_quality" in report
    assert "No permanent provider is selected" in report


def test_render_report_escapes_pipe_characters_in_evidence() -> None:
    results = [
        ProviderTestResult(
            "acme",
            Need.FUNDAMENTALS,
            Criterion.FIELD_COMPLETENESS,
            Outcome.PARTIAL,
            "missing: a | b",
            _NOW,
        )
    ]

    report = render_report(results, _NOW)

    assert "missing: a \\| b" in report


def test_render_report_lists_known_unevaluated_candidates() -> None:
    report = render_report([], _NOW)

    assert "## Known candidates not evaluated this pass" in report
    assert "Polygon.io" in report
    assert "Bloomberg" in report


def test_render_report_sorts_providers_alphabetically() -> None:
    results = [
        ProviderTestResult(
            "zeta", Need.FUNDAMENTALS, Criterion.AUTHENTICATION_SUCCESS, Outcome.PASS, "ok", _NOW
        ),
        ProviderTestResult(
            "alpha", Need.FUNDAMENTALS, Criterion.AUTHENTICATION_SUCCESS, Outcome.PASS, "ok", _NOW
        ),
    ]

    report = render_report(results, _NOW)

    assert report.index("## alpha") < report.index("## zeta")
