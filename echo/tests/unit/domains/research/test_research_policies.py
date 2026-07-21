from datetime import UTC, datetime, timedelta

from domains.research.policies import (
    detect_conflict,
    is_issuer_stale,
    parse_finnhub_issuer_claim,
    parse_sec_edgar_issuer_claim,
    resolve_field,
    resolve_issuer_fields,
)
from domains.research.schemas import ProviderClaim


def test_parse_finnhub_issuer_claim_extracts_expected_fields() -> None:
    raw = {
        "name": "Apple Inc",
        "ticker": "AAPL",
        "finnhubIndustry": "Technology",
        "marketCapitalization": 3000000.0,
    }
    claim = parse_finnhub_issuer_claim(raw)
    assert claim == {"ticker": "AAPL", "name": "Apple Inc", "cik": None, "industry": "Technology"}


def test_parse_sec_edgar_issuer_claim_pads_cik_and_uses_query_ticker() -> None:
    raw = {"name": "Apple Inc.", "cik": 320193, "sicDescription": "ELECTRONIC COMPUTERS"}
    claim = parse_sec_edgar_issuer_claim(raw, ticker="AAPL")
    assert claim == {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "cik": "0000320193",
        "industry": "ELECTRONIC COMPUTERS",
    }


def test_resolve_field_prefers_priority_provider() -> None:
    value, provider = resolve_field("name", {"finnhub": "Apple Inc", "sec_edgar": "Apple Inc."})
    assert value == "Apple Inc."
    assert provider == "sec_edgar"


def test_resolve_field_falls_back_when_priority_provider_missing() -> None:
    value, provider = resolve_field("name", {"finnhub": "Apple Inc"})
    assert value == "Apple Inc"
    assert provider == "finnhub"


def test_resolve_field_ignores_empty_values() -> None:
    value, provider = resolve_field("industry", {"finnhub": "Technology", "sec_edgar": None})
    assert value == "Technology"
    assert provider == "finnhub"


def test_resolve_field_returns_none_when_nothing_available() -> None:
    value, provider = resolve_field("name", {"finnhub": None, "sec_edgar": None})
    assert value is None
    assert provider is None


def test_detect_conflict_flags_real_disagreement() -> None:
    conflict = detect_conflict(
        "name", {"finnhub": "Apple Inc", "sec_edgar": "Apple Inc."}, "Apple Inc.", "sec_edgar"
    )
    assert conflict is not None
    assert conflict.values_by_provider == {"finnhub": "Apple Inc", "sec_edgar": "Apple Inc."}
    assert conflict.resolved_value == "Apple Inc."


def test_detect_conflict_none_when_providers_agree() -> None:
    conflict = detect_conflict(
        "name", {"finnhub": "Apple Inc", "sec_edgar": "Apple Inc"}, "Apple Inc", "sec_edgar"
    )
    assert conflict is None


def test_detect_conflict_none_when_only_one_provider_has_a_value() -> None:
    conflict = detect_conflict(
        "cik", {"finnhub": None, "sec_edgar": "0000320193"}, "0000320193", "sec_edgar"
    )
    assert conflict is None


def _claim(**overrides: object) -> ProviderClaim:
    defaults: dict[str, object] = {
        "issuer_id": "issuer_1",
        "provider": "finnhub",
        "ticker": "AAPL",
        "name": "Apple Inc",
        "cik": None,
        "industry": "Technology",
        "source_record_id": "s1",
        "retrieved_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return ProviderClaim(**defaults)  # type: ignore[arg-type]


def test_resolve_issuer_fields_two_providers_agree_no_conflicts() -> None:
    claims = [
        _claim(provider="finnhub", name="Apple Inc", cik=None, industry="Technology"),
        _claim(
            provider="sec_edgar",
            name="Apple Inc",
            cik="0000320193",
            industry="ELECTRONIC COMPUTERS",
        ),
    ]
    resolved, conflicts = resolve_issuer_fields(claims)
    assert resolved["name"] == "Apple Inc"
    assert resolved["cik"] == "0000320193"
    # industry differs between providers by design (Finnhub's classification
    # vs SEC's SIC description) — a real conflict, not a bug.
    assert any(c.field == "industry" for c in conflicts)
    assert not any(c.field == "name" for c in conflicts)


def test_resolve_issuer_fields_is_deterministic_regardless_of_claim_order() -> None:
    claims_a = [
        _claim(provider="finnhub", name="Apple Inc"),
        _claim(provider="sec_edgar", name="Apple Inc.", cik="0000320193"),
    ]
    claims_b = list(reversed(claims_a))
    resolved_a, _ = resolve_issuer_fields(claims_a)
    resolved_b, _ = resolve_issuer_fields(claims_b)
    assert resolved_a == resolved_b


def test_is_issuer_stale_flags_data_older_than_30_days() -> None:
    updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    assert not is_issuer_stale(updated_at, updated_at + timedelta(days=10))
    assert is_issuer_stale(updated_at, updated_at + timedelta(days=31))
