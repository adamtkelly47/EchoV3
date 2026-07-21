"""Renders the dated provider decision report PROMPT.md Phase 15 requires
("Produce a dated provider decision report with live test evidence").
Pure formatting — no I/O, no live calls; `runner.py` already produced every
`ProviderTestResult` this reads."""

from __future__ import annotations

from datetime import datetime

from scripts.provider_evaluation.metrics import (
    ProviderTestResult,
    group_by_need,
    summarize_provider,
)

# Named providers Docs/DOMAIN_OWNERSHIP.md lists as real Research-domain
# candidates (Polygon, Bloomberg, Reuters) with zero `ProviderTestResult`s
# this pass — no credentials were available to even attempt a request, so
# they never generate a `not_evaluated` result the way a configured-but-
# keyless provider does. Listed explicitly so the report is a complete
# decision input, not a silent omission of what wasn't tried at all.
_KNOWN_UNEVALUATED_CANDIDATES = [
    ("Polygon.io", "market history, fundamentals — no account/API key available this pass"),
    ("Bloomberg", "enterprise-tier pricing data — no account available this pass"),
    ("Reuters", "news — no account/API key available this pass"),
    (
        "an alternate congressional-disclosure source",
        "senate_house_stock_watcher's known public S3 URLs returned HTTP 403 this pass "
        "(see below) — this need still has no working live-tested source",
    ),
]


def _md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_report(results: list[ProviderTestResult], generated_at: datetime) -> str:
    lines = [
        f"# Provider Evaluation Report — {generated_at.date().isoformat()}",
        "",
        "Version: 1.0",
        f"Generated: {generated_at.isoformat()}",
        "Owner: Echo Project",
        "",
        "## Purpose",
        "",
        "PROMPT.md Phase 15: live-tested evaluation of candidate external research data "
        "providers against 13 measured criteria across 8 research needs. Every PASS/FAIL/"
        "PARTIAL outcome below came from an actual request made at generation time, not a "
        "provider's own marketing claim. **No permanent provider is selected by this report** "
        "— that decision belongs to PROMPT.md Phase 16 and beyond.",
        "",
        "Outcomes:",
        "",
        "- `pass` / `fail` / `partial` — from an actual live request.",
        "- `not_evaluated` — no credential was configured for this provider this pass.",
        "- `not_live_testable` — the criterion isn't answerable from a single scripted "
        "request (documentation quality, licensing, cost, schema stability over time, "
        "reliability over time); noted with its source instead of a fabricated score.",
        "",
    ]

    providers = sorted({r.provider for r in results})
    for provider in providers:
        provider_results = [r for r in results if r.provider == provider]
        summary = summarize_provider(provider, results)
        lines.append(f"## {provider}")
        lines.append("")
        needs_text = ", ".join(n.value for n in summary.needs_served) or "none (not evaluated)"
        lines.append(f"**Needs served:** {needs_text}")
        lines.append(
            f"**Summary:** pass={summary.pass_count} fail={summary.fail_count} "
            f"partial={summary.partial_count} not_evaluated={summary.not_evaluated_count} "
            f"not_live_testable={summary.not_live_testable_count}"
        )
        lines.append("")

        by_need = group_by_need(provider_results)
        for need in sorted(by_need, key=lambda n: n.value):
            lines.append(f"### {provider} — {need.value}")
            lines.append("")
            lines.append("| Criterion | Outcome | Evidence |")
            lines.append("|---|---|---|")
            for r in by_need[need]:
                lines.append(
                    f"| {r.criterion.value} | {r.outcome.value} | {_md_escape(r.evidence)} |"
                )
            lines.append("")

        provider_level = [r for r in provider_results if r.need is None]
        if provider_level:
            lines.append(f"### {provider} — provider-level criteria")
            lines.append("")
            lines.append("| Criterion | Outcome | Evidence | Notes |")
            lines.append("|---|---|---|---|")
            for r in provider_level:
                lines.append(
                    f"| {r.criterion.value} | {r.outcome.value} | {_md_escape(r.evidence)} "
                    f"| {_md_escape(r.notes)} |"
                )
            lines.append("")

    lines.append("## Known candidates not evaluated this pass")
    lines.append("")
    lines.append(
        "No credentials were available to even attempt a request against these — "
        "they carry no `ProviderTestResult`s above, not a `not_evaluated` outcome."
    )
    lines.append("")
    for name, note in _KNOWN_UNEVALUATED_CANDIDATES:
        lines.append(f"- **{name}** — {note}")
    lines.append("")

    return "\n".join(lines)
