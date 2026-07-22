"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as domains/portfolio/policies.py.
This is also where each provider's raw JSON (returned as plain dicts by
domains.research.service.ResearchProviderPort, matching the Calendar/
Portfolio precedent of providers speaking in primitives) gets translated
into Research's own vocabulary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.identifiers import new_id
from domains.research.schemas import (
    AnomalyFeature,
    EventType,
    FieldConflict,
    InsiderProfile,
    InsiderTransaction,
    NewsArticle,
    ProviderClaim,
    TransactionType,
)

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


def parse_finnhub_news_articles(
    raw: list[dict[str, Any]], *, issuer_id: str, source_record_id: str, synced_at: datetime
) -> list[NewsArticle]:
    """Finnhub's `/company-news` response, live-verified in Phase 15
    (Docs/DECISION_LOG.md's Phase 15 entry: real free-tier access
    confirmed). An item missing a headline, url, or timestamp is skipped
    rather than half-recorded. `cluster_id` starts as each article's own id
    — standalone until `cluster_duplicates` runs."""
    articles = []
    for item in raw:
        headline = str(item.get("headline", "")).strip()
        url = str(item.get("url", "")).strip()
        epoch = item.get("datetime")
        if not headline or not url or epoch is None:
            continue
        article_id = new_id("article")
        articles.append(
            NewsArticle(
                article_id=article_id,
                issuer_id=issuer_id,
                headline=headline,
                blurb=str(item.get("summary") or "").strip() or None,
                source=str(item.get("source", "unknown")),
                url=url,
                published_at=datetime.fromtimestamp(epoch, tz=UTC),
                source_record_id=source_record_id,
                cluster_id=article_id,
                synced_at=synced_at,
            )
        )
    return articles


# PROMPT.md Phase 17 implement item 2: "source quality policy." An explicit,
# static table rather than a model guess (CONSTITUTION.md: deterministic
# calculations belong in code). An unrecognized source gets a conservative
# default rather than being assumed reputable.
_SOURCE_QUALITY_SCORES: dict[str, float] = {
    "reuters": 1.0,
    "bloomberg": 1.0,
    "associated press": 0.95,
    "the wall street journal": 0.95,
    "cnbc": 0.85,
    "marketwatch": 0.8,
    "yahoo": 0.7,
    "seeking alpha": 0.6,
    "motley fool": 0.55,
    "benzinga": 0.5,
    # Wire services distributing companies' own press releases — accurate
    # (they're the company's own words) but promotional, not independent
    # reporting, so scored below independent financial press.
    "pr newswire": 0.5,
    "business wire": 0.5,
    "globenewswire": 0.5,
}
_DEFAULT_SOURCE_QUALITY = 0.4


def source_quality_score(source: str) -> float:
    return _SOURCE_QUALITY_SCORES.get(source.strip().lower(), _DEFAULT_SOURCE_QUALITY)


_CLUSTER_TIME_WINDOW = timedelta(hours=48)
_CLUSTER_SIMILARITY_THRESHOLD = 0.5
_HEADLINE_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "is", "at", "as", "with", "by",
}  # fmt: skip


def _headline_tokens(headline: str) -> set[str]:
    cleaned = "".join(c.lower() if c.isalnum() or c.isspace() else " " for c in headline)
    return {w for w in cleaned.split() if w not in _HEADLINE_STOPWORDS}


def _headline_similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = _headline_tokens(a), _headline_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def cluster_duplicates(articles: list[NewsArticle]) -> list[NewsArticle]:
    """PROMPT.md Phase 17 implement item 4: "duplicate clustering." No
    model call — deterministic headline-similarity (Jaccard over
    non-stopword tokens) plus time-proximity, exactly the kind of decision
    CONSTITUTION.md says belongs in code, not a model guess. The cluster's
    primary is the highest-source-quality member, ties broken by earliest
    publication (verification 1: "duplicate stories collapse" — only the
    primary is ever surfaced downstream, via `select_top_stories`).

    A known simplification, not silently hidden: this is single-pass greedy
    clustering, not full transitive closure — if A matches B and B matches
    C but A doesn't directly match C, all three still end up in one cluster
    here (A's pass absorbs both), which is the same practical outcome full
    transitive clustering would reach for this phase's real, small article
    counts, without the added complexity of a union-find structure."""
    result: list[NewsArticle] = []
    assigned: set[str] = set()
    for i, article in enumerate(articles):
        if article.article_id in assigned:
            continue
        cluster_members = [article]
        for other in articles[i + 1 :]:
            if other.article_id in assigned:
                continue
            if abs(other.published_at - article.published_at) > _CLUSTER_TIME_WINDOW:
                continue
            if (
                _headline_similarity(article.headline, other.headline)
                >= _CLUSTER_SIMILARITY_THRESHOLD
            ):
                cluster_members.append(other)
        primary = min(
            cluster_members, key=lambda a: (-source_quality_score(a.source), a.published_at)
        )
        for member in cluster_members:
            assigned.add(member.article_id)
            result.append(
                member.model_copy(
                    update={
                        "cluster_id": primary.article_id,
                        "is_cluster_primary": member.article_id == primary.article_id,
                    }
                )
            )
    return result


# PROMPT.md Phase 17 implement item 6 input: how materially significant an
# event type generally is — earnings/M&A/guidance move markets; routine
# product news rarely does. A static table, same rationale as source
# quality above.
_EVENT_TYPE_WEIGHTS: dict[EventType, float] = {
    EventType.EARNINGS: 1.0,
    EventType.MERGER_ACQUISITION: 1.0,
    EventType.GUIDANCE: 0.9,
    EventType.REGULATORY: 0.9,
    EventType.LITIGATION: 0.8,
    EventType.LEADERSHIP_CHANGE: 0.7,
    EventType.PRODUCT: 0.5,
    EventType.OTHER: 0.3,
}

_RECENCY_HALF_LIFE = timedelta(days=3)
_PORTFOLIO_HOLDING_BOOST = 1.5
_MIN_RELEVANCE_THRESHOLD = 0.15


def event_type_weight(event_type: EventType | None) -> float:
    return _EVENT_TYPE_WEIGHTS[event_type or EventType.OTHER]


def _recency_factor(published_at: datetime, now: datetime) -> float:
    age = now - published_at
    if age.total_seconds() <= 0:
        return 1.0
    half_lives = age / _RECENCY_HALF_LIFE
    return float(0.5**half_lives)


def compute_relevance_score(
    article: NewsArticle, *, is_portfolio_holding: bool, now: datetime
) -> float:
    """PROMPT.md Phase 17 implement item 6: "relevance scoring" — a
    deterministic combination, not a model guess (CONSTITUTION.md).
    Implement item 7 ("portfolio and thesis matching"): `is_portfolio_holding`
    is computed by application/orchestrators/news_intelligence.py from the
    real, synced Portfolio domain (Application-layer cross-domain query,
    per Docs/DOMAIN_OWNERSHIP.md's Cross-Domain Interaction Matrix —
    Portfolio-Research only via Application Query, never a direct
    domain-to-domain call). Thesis matching is *not* applied here — no
    Investment Thesis storage exists yet; this is a documented gap
    (Docs/DECISION_LOG.md's Phase 17 entry), not a fabricated boost."""
    base = source_quality_score(article.source) * event_type_weight(article.event_type)
    score = base * _recency_factor(article.published_at, now)
    if is_portfolio_holding:
        # PROMPT.md Phase 17 verification 3: material portfolio news must
        # outrank generic popularity.
        score *= _PORTFOLIO_HOLDING_BOOST
    return round(score, 4)


def suppress_low_relevance(
    articles: list[NewsArticle], threshold: float = _MIN_RELEVANCE_THRESHOLD
) -> list[NewsArticle]:
    """PROMPT.md Phase 17 verification 2: "low relevance trending stories
    are suppressed." """
    return [a for a in articles if (a.relevance_score or 0.0) >= threshold]


def select_top_stories(articles: list[NewsArticle], limit: int = 5) -> list[NewsArticle]:
    """PROMPT.md Phase 17's own objective: "surface a small amount of
    materially relevant news." Only cluster primaries are eligible
    (verification 1: duplicate stories collapse — a near-duplicate should
    never occupy a second slot in the final small set)."""
    primaries = [a for a in articles if a.is_cluster_primary]
    ranked = sorted(primaries, key=lambda a: a.relevance_score or 0.0, reverse=True)
    return ranked[:limit]


# PROMPT.md Phase 18 implement item 4: "transaction type normalization."
# Real SEC transaction codes, live-verified against several real UnitedHealth
# Group Form 4 filings before this table was written (Docs/DECISION_LOG.md's
# Phase 18 entry) — A (grant/award) and S (open market sale) both actually
# observed; the rest are well-documented SEC conventions not yet seen live in
# this codebase's own test filings, mapped from SEC's own published code list
# rather than assumed. Any code not in this table is TransactionType.OTHER,
# never a guess.
_TRANSACTION_CODE_MAP: dict[str, TransactionType] = {
    "P": TransactionType.OPEN_MARKET_PURCHASE,
    "S": TransactionType.OPEN_MARKET_SALE,
    "A": TransactionType.GRANT_AWARD,
    "M": TransactionType.OPTION_EXERCISE,
    "X": TransactionType.OPTION_EXERCISE,
    "F": TransactionType.TAX_WITHHOLDING,
    "G": TransactionType.GIFT,
}


def normalize_transaction_type(transaction_code: str) -> TransactionType:
    return _TRANSACTION_CODE_MAP.get(transaction_code, TransactionType.OTHER)


def parse_form4_transactions(
    raw: dict[str, Any],
    *,
    issuer_id: str,
    accession_number: str,
    source_record_id: str,
    now: datetime,
) -> list[InsiderTransaction]:
    """Translates one filing's raw dict (`providers.research.sec_edgar.
    adapter._parse_form4_xml`'s output) into typed, normalized transactions.
    PROMPT.md Phase 18 implement item 3 ("insider identity normalization"):
    the reporting owner's CIK/name/role are attached to every transaction
    in the filing, uniformly. Verification 2 ("planned sales are identified
    when data supports it"): `is_planned_sale` is only ever `True` when the
    filing's own `aff10b5_one` flag says so — never inferred from anything
    else. A transaction missing a required field (date, code, or share
    count) is skipped rather than half-recorded, matching every other
    parser in this codebase.

    `transaction_id` is derived deterministically from `(accession_number,
    index-within-filing)` rather than `InsiderTransaction`'s own random
    default — a filing's own transaction ordering is stable across
    re-fetches, and SEC provides no other per-transaction identifier. This
    is load-bearing: `ResearchRepository.save_insider_transactions` upserts
    by `transaction_id` (the same enrich-in-place pattern as `save_articles`),
    so re-ingesting an already-seen filing (any scheduled re-sync will, since
    `get_form4_filings` always returns the most recent N) must resolve to the
    *same* rows, not duplicate ones — duplicated history would silently
    corrupt `compute_insider_profile` and `compute_size_anomaly`'s baselines.
    Caught live (Docs/DECISION_LOG.md's Phase 18 entry) by re-running
    ingestion against real UNH filings twice with overlapping accessions and
    observing duplicate rows before this fix."""
    insider_cik = raw.get("reporting_owner_cik")
    insider_name = raw.get("reporting_owner_name")
    if not insider_cik or not insider_name:
        return []
    aff10b5_one = bool(raw.get("aff10b5_one", False))
    footnotes: dict[str, str] = raw.get("footnotes", {})

    transactions = []
    for index, item in enumerate(raw.get("transactions", [])):
        date_str = item.get("transaction_date")
        code = item.get("transaction_code")
        shares_str = item.get("shares")
        if not date_str or not code or shares_str is None:
            continue
        try:
            shares = float(shares_str)
            transaction_date = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
        price_str = item.get("price_per_share")
        price = float(price_str) if price_str not in (None, "") else None
        transaction_type = normalize_transaction_type(code)
        footnote_ids = item.get("footnote_ids") or []
        footnote_text = " ".join(footnotes[fid] for fid in footnote_ids if fid in footnotes) or None

        transactions.append(
            InsiderTransaction(
                transaction_id=f"insidertxn_{accession_number}_{index}",
                issuer_id=issuer_id,
                insider_cik=str(insider_cik),
                insider_name=str(insider_name),
                is_director=bool(raw.get("is_director", False)),
                is_officer=bool(raw.get("is_officer", False)),
                is_ten_percent_owner=bool(raw.get("is_ten_percent_owner", False)),
                officer_title=raw.get("officer_title"),
                transaction_date=transaction_date,
                transaction_code=code,
                transaction_type=transaction_type,
                shares=shares,
                price_per_share=price,
                transaction_value=compute_transaction_value(shares, price),
                acquired_disposed=str(item.get("acquired_disposed") or ""),
                shares_owned_after=(
                    float(item["shares_owned_following"])
                    if item.get("shares_owned_following") not in (None, "")
                    else None
                ),
                ownership_change_percent=compute_ownership_change_percent(
                    shares,
                    float(item["shares_owned_following"])
                    if item.get("shares_owned_following") not in (None, "")
                    else None,
                    item.get("acquired_disposed"),
                ),
                is_planned_sale=(
                    transaction_type == TransactionType.OPEN_MARKET_SALE and aff10b5_one
                ),
                footnote_text=footnote_text,
                filing_accession_number=accession_number,
                source_record_id=source_record_id,
                synced_at=now,
            )
        )
    return transactions


def compute_transaction_value(shares: float, price_per_share: float | None) -> float | None:
    """PROMPT.md Phase 18 verification 3: "transaction values ... are
    computed in code." `None` (never `0` or a guess) when the filing itself
    didn't report a price — a stock grant genuinely has no market price,
    and that stays missing rather than being estimated (Docs/DATA_MODEL.md:
    Negative and Missing Data)."""
    if price_per_share is None:
        return None
    return round(shares * price_per_share, 2)


def compute_ownership_change_percent(
    shares_transacted: float, shares_owned_after: float | None, acquired_disposed: str | None
) -> float | None:
    """PROMPT.md Phase 18 verification 3: "ownership changes are computed
    in code." Derives the pre-transaction holding from the filing's own
    post-transaction figure and the transacted share count — both real,
    filing-reported numbers, never estimated. `None` when the filing didn't
    report a post-transaction balance."""
    if shares_owned_after is None:
        return None
    shares_owned_before = (
        shares_owned_after - shares_transacted
        if acquired_disposed == "A"
        else shares_owned_after + shares_transacted
    )
    if shares_owned_before <= 0:
        return None
    return round((shares_transacted / shares_owned_before) * 100, 2)


# PROMPT.md Phase 18 implement item 7: "deterministic anomaly features."
# Docs/DOMAIN_OWNERSHIP.md's Research domain business rules explicitly name
# "personal baseline anomaly detection" — compared against the insider's
# *own* history, never a market-wide or peer benchmark this phase has no
# real data for.
_SIZE_ANOMALY_RATIO_THRESHOLD = 3.0
_CLUSTER_WINDOW = timedelta(days=7)
_CLUSTER_INSIDER_THRESHOLD = 3


def compute_size_anomaly(
    transaction: InsiderTransaction, insider_history: list[InsiderTransaction]
) -> AnomalyFeature | None:
    """PROMPT.md Phase 18 verification 4: "anomaly claims explain the
    comparison baseline." `baseline_description` states exactly what was
    compared against what — never a bare score. Requires at least 2 prior
    transactions to establish a real baseline; with fewer, there's nothing
    honest to compare against, so no feature is produced at all (not a
    fabricated one)."""
    prior = [
        t
        for t in insider_history
        if t.transaction_id != transaction.transaction_id
        and t.transaction_date < transaction.transaction_date
    ]
    if len(prior) < 2:
        return None
    average_shares = sum(t.shares for t in prior) / len(prior)
    if average_shares <= 0:
        return None
    ratio = round(transaction.shares / average_shares, 2)
    return AnomalyFeature(
        feature_name="transaction_size_vs_personal_baseline",
        value=ratio,
        baseline_description=(
            f"this transaction is {ratio}x the insider's own average transaction size "
            f"({round(average_shares, 2)} shares) across their {len(prior)} prior recorded "
            f"transactions for this issuer"
        ),
        is_notable=ratio >= _SIZE_ANOMALY_RATIO_THRESHOLD,
    )


def compute_insider_cluster_feature(
    transaction: InsiderTransaction, issuer_transactions: list[InsiderTransaction]
) -> AnomalyFeature | None:
    """A real, well-known signal — multiple distinct insiders transacting
    in the same direction within a short window — computed here as a count
    with an explicit, stated window and comparison set (verification 4),
    never a bare "cluster detected" flag."""
    window_start = transaction.transaction_date - _CLUSTER_WINDOW
    window_end = transaction.transaction_date + _CLUSTER_WINDOW
    same_direction = {
        t.insider_cik
        for t in issuer_transactions
        if t.acquired_disposed == transaction.acquired_disposed
        and window_start <= t.transaction_date <= window_end
    }
    count = len(same_direction)
    direction = "sales" if transaction.acquired_disposed == "D" else "acquisitions"
    return AnomalyFeature(
        feature_name="insider_cluster_timing",
        value=float(count),
        baseline_description=(
            f"{count} distinct insider(s) at this issuer recorded a {direction[:-1]} transaction "
            f"within {_CLUSTER_WINDOW.days} days of this one (including this transaction's own "
            "insider)"
        ),
        is_notable=count >= _CLUSTER_INSIDER_THRESHOLD,
    )


def compute_insider_profile(
    insider_cik: str, insider_name: str, issuer_id: str, transactions: list[InsiderTransaction]
) -> InsiderProfile | None:
    """PROMPT.md Phase 18 implement item 6: "historical insider profile."
    `None` when there's no transaction history at all — an empty profile
    would be a fabricated zero, not an honest absence."""
    if not transactions:
        return None
    purchased = sum(
        t.transaction_value or 0.0
        for t in transactions
        if t.transaction_type == TransactionType.OPEN_MARKET_PURCHASE
    )
    sold = sum(
        t.transaction_value or 0.0
        for t in transactions
        if t.transaction_type == TransactionType.OPEN_MARKET_SALE
    )
    dates = [t.transaction_date for t in transactions]
    return InsiderProfile(
        insider_cik=insider_cik,
        insider_name=insider_name,
        issuer_id=issuer_id,
        transaction_count=len(transactions),
        total_purchased_value=round(purchased, 2),
        total_sold_value=round(sold, 2),
        average_transaction_shares=round(
            sum(t.shares for t in transactions) / len(transactions), 2
        ),
        first_transaction_date=min(dates),
        last_transaction_date=max(dates),
    )
