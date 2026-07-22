from datetime import UTC, datetime, timedelta

from domains.research.policies import (
    cluster_duplicates,
    compute_relevance_score,
    detect_conflict,
    event_type_weight,
    is_issuer_stale,
    parse_finnhub_issuer_claim,
    parse_finnhub_news_articles,
    parse_sec_edgar_issuer_claim,
    resolve_field,
    resolve_issuer_fields,
    select_top_stories,
    source_quality_score,
    suppress_low_relevance,
)
from domains.research.schemas import EventType, NewsArticle, ProviderClaim


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


def test_parse_finnhub_news_articles_extracts_expected_fields() -> None:
    raw = [
        {
            "headline": "Company beats earnings estimates",
            "summary": "A short blurb about the earnings beat.",
            "source": "Reuters",
            "url": "https://example.com/1",
            "datetime": 1767225600,
        },
        {
            # Missing url — must be skipped, not half-recorded.
            "headline": "Incomplete article",
            "source": "Reuters",
            "datetime": 1767225600,
        },
    ]
    articles = parse_finnhub_news_articles(
        raw, issuer_id="issuer_1", source_record_id="s1", synced_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert len(articles) == 1
    assert articles[0].headline == "Company beats earnings estimates"
    assert articles[0].blurb == "A short blurb about the earnings beat."
    assert articles[0].source == "Reuters"
    assert articles[0].cluster_id == articles[0].article_id  # standalone until clustered


def test_source_quality_score_known_and_unknown_sources() -> None:
    assert source_quality_score("Reuters") == 1.0
    assert source_quality_score("reuters") == 1.0  # case-insensitive
    assert source_quality_score("Some Random Blog") == 0.4  # conservative default


def _article(**overrides: object) -> NewsArticle:
    defaults: dict[str, object] = {
        "issuer_id": "issuer_1",
        "headline": "Company beats earnings estimates",
        "source": "Reuters",
        "url": "https://example.com/1",
        "published_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "source_record_id": "s1",
        "cluster_id": "placeholder",
        "synced_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    article = NewsArticle(**defaults)  # type: ignore[arg-type]
    if "cluster_id" not in overrides:
        article = article.model_copy(update={"cluster_id": article.article_id})
    return article


def test_cluster_duplicates_collapses_similar_headlines_within_time_window() -> None:
    """PROMPT.md Phase 17 verification 1: duplicate stories collapse."""
    a = _article(headline="Company beats Q3 earnings estimates", source="Reuters")
    b = _article(
        headline="Company beats Q3 earnings estimates handily",
        source="Some Random Blog",
        published_at=a.published_at + timedelta(hours=2),
    )
    clustered = cluster_duplicates([a, b])
    cluster_ids = {c.cluster_id for c in clustered}
    assert len(cluster_ids) == 1  # collapsed into one cluster
    primaries = [c for c in clustered if c.is_cluster_primary]
    assert len(primaries) == 1
    assert primaries[0].source == "Reuters"  # higher source quality wins


def test_cluster_duplicates_keeps_unrelated_headlines_separate() -> None:
    a = _article(headline="Company beats Q3 earnings estimates")
    b = _article(headline="Regulator opens investigation into pricing practices")
    clustered = cluster_duplicates([a, b])
    assert len({c.cluster_id for c in clustered}) == 2
    assert all(c.is_cluster_primary for c in clustered)


def test_cluster_duplicates_keeps_similar_headlines_separate_outside_time_window() -> None:
    a = _article(headline="Company beats Q3 earnings estimates")
    b = _article(
        headline="Company beats Q3 earnings estimates handily",
        published_at=a.published_at + timedelta(days=10),
    )
    clustered = cluster_duplicates([a, b])
    assert len({c.cluster_id for c in clustered}) == 2


def test_event_type_weight_earnings_outweighs_product() -> None:
    assert event_type_weight(EventType.EARNINGS) > event_type_weight(EventType.PRODUCT)
    assert event_type_weight(None) == event_type_weight(EventType.OTHER)


def test_compute_relevance_score_portfolio_holding_outranks_generic_popularity() -> None:
    """PROMPT.md Phase 17 verification 3: material portfolio news outranks
    generic popularity — a held ticker's earnings news must outscore a
    non-held ticker's higher-source-quality but non-material story."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    held = _article(
        source="Benzinga", event_type=EventType.EARNINGS, published_at=now
    )  # lower-quality source, but a real holding
    not_held = _article(
        source="Reuters", event_type=EventType.PRODUCT, published_at=now
    )  # higher-quality source, generic popularity, not held

    held_score = compute_relevance_score(held, is_portfolio_holding=True, now=now)
    not_held_score = compute_relevance_score(not_held, is_portfolio_holding=False, now=now)
    assert held_score > not_held_score


def test_compute_relevance_score_decays_with_age() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    fresh = _article(published_at=now)
    stale = _article(published_at=now - timedelta(days=30))
    fresh_score = compute_relevance_score(fresh, is_portfolio_holding=False, now=now)
    stale_score = compute_relevance_score(stale, is_portfolio_holding=False, now=now)
    assert fresh_score > stale_score


def test_suppress_low_relevance_filters_below_threshold() -> None:
    """PROMPT.md Phase 17 verification 2: low relevance trending stories
    are suppressed."""
    high = _article(relevance_score=0.8)
    low = _article(relevance_score=0.01)
    survivors = suppress_low_relevance([high, low])
    assert survivors == [high]


def test_select_top_stories_only_includes_cluster_primaries_and_respects_limit() -> None:
    primary = _article(relevance_score=0.9)
    duplicate = _article(relevance_score=0.95).model_copy(
        update={"cluster_id": primary.article_id, "is_cluster_primary": False}
    )
    other = _article(relevance_score=0.5)
    top = select_top_stories([primary, duplicate, other], limit=1)
    assert len(top) == 1
    assert top[0].article_id == primary.article_id  # not the higher-scored non-primary duplicate
