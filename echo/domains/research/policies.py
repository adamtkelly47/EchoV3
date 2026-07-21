"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as domains/portfolio/policies.py.
This is also where each provider's raw JSON (returned as plain dicts by
domains.research.service.ResearchProviderPort, matching the Calendar/
Portfolio precedent of providers speaking in primitives) gets translated
into Research's own vocabulary.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from domains.research.schemas import FieldConflict, ProviderClaim

# Research data (a company's name, industry classification) changes far
# slower than portfolio positions — a 30-day threshold, not Portfolio's
# 24-hour one (domains/portfolio/policies.py's `_STALENESS_THRESHOLD`).
_STALENESS_THRESHOLD = timedelta(days=30)

# PROMPT.md Phase 16 implement item 10: "provider fallback rules." SEC's
# legal name and SIC-derived data are authoritative where SEC actually
# provides them; Finnhub is preferred for fields SEC doesn't return at all
# (an industry classification suitable for display, and it's the only
# provider that supplies one this phase — SEC's `sicDescription` is a
# regulatory classification, kept as a distinct, visible alternative rather
# than assumed equivalent). Verified live which provider actually returns
# which field before writing this table (Docs/DECISION_LOG.md's Phase 16
# entry), not assumed from documentation alone.
_FIELD_PROVIDER_PRIORITY: dict[str, list[str]] = {
    "name": ["sec_edgar", "finnhub"],
    "industry": ["finnhub", "sec_edgar"],
    "cik": ["sec_edgar"],
}

_RESOLVABLE_FIELDS = ["name", "cik", "industry"]


def parse_finnhub_issuer_claim(raw: dict[str, Any]) -> dict[str, Any]:
    """Finnhub's `/stock/profile2` response, live-verified in Phase 15
    (Docs/DECISION_LOG.md's Phase 15 entry: 23/28 criteria passed for
    fundamentals). No CIK field exists in this response."""
    return {
        "ticker": str(raw.get("ticker", "")),
        "name": raw.get("name") or None,
        "cik": None,
        "industry": raw.get("finnhubIndustry") or None,
    }


def parse_sec_edgar_issuer_claim(raw: dict[str, Any], *, ticker: str) -> dict[str, Any]:
    """SEC EDGAR's `/submissions/CIK{cik}.json` response, live-verified in
    Phase 15. `ticker` is passed in separately — the submissions response
    itself lists every ticker/exchange pair a CIK has ever used, not "the"
    single ticker being queried, so the caller's own query ticker is used
    instead of trying to pick one out of that list."""
    cik = raw.get("cik")
    return {
        "ticker": ticker,
        "name": raw.get("name") or None,
        "cik": str(cik).zfill(10) if cik is not None else None,
        "industry": raw.get("sicDescription") or None,
    }


def resolve_field(
    field: str, claims_by_provider: dict[str, str | None]
) -> tuple[str | None, str | None]:
    """PROMPT.md Phase 16 implement item 10. Returns (resolved_value,
    resolved_from_provider). Falls through the priority list first; any
    provider not in the priority list (a future, not-yet-ranked provider)
    is still usable as a last resort rather than silently dropped."""
    priority = _FIELD_PROVIDER_PRIORITY.get(field, [])
    for provider in priority:
        value = claims_by_provider.get(provider)
        if value:
            return value, provider
    for provider, value in claims_by_provider.items():
        if value:
            return value, provider
    return None, None


def detect_conflict(
    field: str,
    claims_by_provider: dict[str, str | None],
    resolved_value: str | None,
    resolved_from_provider: str | None,
) -> FieldConflict | None:
    """PROMPT.md Phase 16 verification 2: "source conflicts remain
    visible." A conflict exists whenever two providers claimed *different*
    non-empty values for the same field — resolving to one value never
    erases that the other provider said something else."""
    present = {p: v for p, v in claims_by_provider.items() if v}
    if len({v for v in present.values()}) <= 1:
        return None
    return FieldConflict(
        field=field,
        values_by_provider=present,
        resolved_value=resolved_value or "",
        resolved_from_provider=resolved_from_provider or "",
    )


def resolve_issuer_fields(
    claims: list[ProviderClaim],
) -> tuple[dict[str, str | None], list[FieldConflict]]:
    """Always recomputed from *every* claim ever recorded for an issuer,
    never incrementally patched — re-running with the same claims always
    produces the same result (PROMPT.md Phase 16 verification 1: two
    providers deterministically map into the same schema), and a claim from
    a provider that's since started failing is still honored rather than
    silently dropped just because today's sync didn't reach it."""
    resolved: dict[str, str | None] = {}
    conflicts: list[FieldConflict] = []
    for field in _RESOLVABLE_FIELDS:
        claims_by_provider = {c.provider: getattr(c, field) for c in claims}
        value, from_provider = resolve_field(field, claims_by_provider)
        resolved[field] = value
        conflict = detect_conflict(field, claims_by_provider, value, from_provider)
        if conflict:
            conflicts.append(conflict)
    return resolved, conflicts


def is_issuer_stale(updated_at: datetime, now: datetime) -> bool:
    return now - updated_at > _STALENESS_THRESHOLD
