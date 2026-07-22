"""Research's own data contracts (Docs/DOMAIN_OWNERSHIP.md: Research owns
"Company Profiles", "Security Master", "Tickers", "Identifiers", "Evidence
Provenance"). PROMPT.md Phase 16's objective is "provider independent
research storage" — `Issuer`/`SecurityMasterEntry` are the provider-agnostic,
merged view; `ProviderClaim` preserves exactly what each individual provider
said, so a disagreement between providers is never silently discarded
(verification 2: "source conflicts remain visible").
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from core.identifiers import new_id


class EventType(str, Enum):
    """PROMPT.md Phase 17 implement item 5: "event type classification
    through Ollama." A fixed, closed vocabulary — the model picks exactly
    one of these (`application/orchestrators/news_intelligence.py`'s
    structured-output call), it never free-text generates a category, which
    is what makes verification 5 ("the local model cannot silently invent
    facts") true by construction here rather than by prompt instruction
    alone."""

    EARNINGS = "earnings"
    MERGER_ACQUISITION = "merger_acquisition"
    LEADERSHIP_CHANGE = "leadership_change"
    REGULATORY = "regulatory"
    GUIDANCE = "guidance"
    PRODUCT = "product"
    LITIGATION = "litigation"
    OTHER = "other"


class ProviderClaim(BaseModel):
    """What one provider said about one issuer, at one point in time —
    immutable once recorded (Docs/DATA_MODEL.md: Immutability). Never
    overwritten by a later claim from the same or a different provider;
    a new sync creates a new claim, matching PortfolioSnapshot's precedent
    of "new sync, new row" rather than mutating history."""

    claim_id: str = Field(default_factory=lambda: new_id("claim"))
    issuer_id: str
    provider: str
    ticker: str
    name: str | None = None
    cik: str | None = None
    industry: str | None = None
    source_record_id: str
    retrieved_at: datetime


class FieldConflict(BaseModel):
    """PROMPT.md Phase 16 verification 2: "source conflicts remain
    visible." Recorded whenever two providers' claims disagree on the same
    field for the same issuer — `resolved_value` is what
    `domains.research.policies.resolve_field`'s provider-priority rules
    chose, but every provider's own claimed value stays visible alongside
    it, not overwritten."""

    field: str
    values_by_provider: dict[str, str]
    resolved_value: str
    resolved_from_provider: str


class Issuer(BaseModel):
    """Echo's own stable representation of a real-world company —
    independent of any single provider's identifier scheme (PROMPT.md Phase
    16 implement item 2: "issuer identity"). `cik` is SEC's identifier, kept
    as a first-class field (not a generic identifier map) because it's the
    one cross-provider identifier this phase actually has and needs to
    query by — Docs/DECISION_LOG.md's Phase 16 entry explains why a generic
    identifiers dict was deliberately not built ahead of a second identifier
    type actually being needed (No Future Scaffolding)."""

    issuer_id: str = Field(default_factory=lambda: new_id("issuer"))
    name: str
    cik: str | None = None
    primary_ticker: str | None = None
    industry: str | None = None
    # Lineage (PROMPT.md Phase 16 verification 4: "every normalized item
    # retains source lineage") — every SourceRecord that ever contributed
    # to this issuer's current resolved field values.
    source_record_ids: list[str] = Field(default_factory=list)
    conflicts: list[FieldConflict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SecurityMasterEntry(BaseModel):
    """A specific tradable security belonging to an `Issuer` (PROMPT.md
    Phase 16 implement item 1: "security master") — kept distinct from
    `Issuer` per Docs/DOMAIN_OWNERSHIP.md's own separate listing of
    "Security Master" and "Company Profiles", since one issuer can in
    principle have more than one listed security (e.g. multiple share
    classes) even though this phase's real data has exactly one each."""

    security_id: str = Field(default_factory=lambda: new_id("security"))
    issuer_id: str
    ticker: str
    exchange: str | None = None
    active: bool = True
    source_record_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EvidencePackage(BaseModel):
    """PROMPT.md Phase 16 implement item 9: "evidence package generation" —
    "show your work" for any displayed research fact (CONSTITUTION.md:
    Provenance). Bundles the resolved `Issuer`, its securities, every raw
    `ProviderClaim` that contributed (so a conflict is visible in context,
    not just as an isolated `FieldConflict` list), and freshness."""

    issuer: Issuer
    securities: list[SecurityMasterEntry]
    claims: list[ProviderClaim]
    is_stale: bool
    generated_at: datetime


class NewsArticle(BaseModel):
    """A single ingested article (PROMPT.md Phase 17 implement item 1).
    `cluster_id` groups near-duplicate stories together
    (`domains.research.policies.cluster_duplicates` — implement item 4);
    a standalone article's own `article_id` is its `cluster_id`.
    `event_type`/`summary`/`relevance_score` start `None` at ingestion and
    are filled in by later pipeline stages (classification, summarization,
    scoring) — `application/orchestrators/news_intelligence.py` owns that
    sequencing since it needs the Model Gateway, which domains/ never
    imports (CONSTITUTION.md dependency direction)."""

    article_id: str = Field(default_factory=lambda: new_id("article"))
    issuer_id: str
    headline: str
    # The provider's own short description, when it supplies one — real
    # input text for the Ollama summarization step (`summary` below),
    # distinct from it: this is what the provider said, `summary` is what
    # the local model said about it.
    blurb: str | None = None
    source: str
    url: str
    published_at: datetime
    source_record_id: str
    cluster_id: str
    is_cluster_primary: bool = True
    event_type: EventType | None = None
    summary: str | None = None
    relevance_score: float | None = None
    synced_at: datetime


class NewsDigest(BaseModel):
    """PROMPT.md Phase 17's stated objective: "surface a small amount of
    materially relevant news." The final, small, ranked set of articles
    plus Claude's synthesized narrative (implement item 9) — `narrative`
    must cite back into `article_ids` (verification 4: "the final narrative
    links back to evidence"), checked live, not just instructed in the
    prompt (Docs/DECISION_LOG.md's Phase 17 entry)."""

    digest_id: str = Field(default_factory=lambda: new_id("digest"))
    issuer_id: str
    article_ids: list[str]
    narrative: str
    generated_at: datetime


class NewsFeedback(BaseModel):
    """PROMPT.md Phase 17 implement item 10: "user feedback signals."
    Recorded but not yet consumed by relevance scoring — closing this loop
    is future work, noted honestly rather than claimed done
    (Docs/DECISION_LOG.md's Phase 17 entry)."""

    feedback_id: str = Field(default_factory=lambda: new_id("newsfeedback"))
    article_id: str
    user_id: str
    useful: bool
    created_at: datetime


class TransactionType(str, Enum):
    """PROMPT.md Phase 18 implement item 4: "transaction type
    normalization." A fixed, closed vocabulary the raw SEC transaction code
    is mapped into by `domains.research.policies.normalize_transaction_type`
    — never inferred by a model. Verification 1 ("grants and open market
    purchases are distinguished") is true by construction: `GRANT_AWARD` and
    `OPEN_MARKET_PURCHASE` are different values, never conflated."""

    OPEN_MARKET_PURCHASE = "open_market_purchase"  # code P
    OPEN_MARKET_SALE = "open_market_sale"  # code S
    GRANT_AWARD = "grant_award"  # code A
    OPTION_EXERCISE = "option_exercise"  # codes M, X
    TAX_WITHHOLDING = "tax_withholding"  # code F
    GIFT = "gift"  # code G
    OTHER = "other"  # any other real SEC code (C, D, ...) — never guessed


class FilingContext(str, Enum):
    """PROMPT.md Phase 18 implement item 8: "local filing context
    classification." Closed vocabulary Ollama classifies a transaction's
    real footnote text into (when one exists) — never free-text generation,
    same structural-safety pattern as Phase 17's `EventType`."""

    ROUTINE_COMPENSATION = "routine_compensation"
    TAX_WITHHOLDING_EXPLANATION = "tax_withholding_explanation"
    GIFT_EXPLANATION = "gift_explanation"
    PLAN_10B5_1_EXPLANATION = "plan_10b5_1_explanation"
    OTHER_EXPLANATION = "other_explanation"
    NO_FOOTNOTE = "no_footnote"


class InsiderTransaction(BaseModel):
    """One non-derivative transaction from one Form 4 filing (PROMPT.md
    Phase 18 implement items 2-5). `derivativeTable` (options/derivatives)
    is deliberately not parsed — a documented scope limitation
    (Docs/DECISION_LOG.md's Phase 18 entry), not a silent gap.
    `transaction_value`/`ownership_change_percent` are computed in code from
    the filing's own reported numbers (verification 3: "transaction values
    and ownership changes are computed in code") — never estimated when the
    filing itself doesn't report a price (a stock grant's `price_per_share`
    is genuinely `0` or absent, and stays that way, matching Portfolio's
    established "missing stays missing" discipline). `is_planned_sale` is
    only ever `True` when the filing's own `aff10b5One` flag says so
    (verification 2: "planned sales are identified when data supports it")
    — never inferred."""

    transaction_id: str = Field(default_factory=lambda: new_id("insidertxn"))
    issuer_id: str
    insider_cik: str
    insider_name: str
    is_director: bool
    is_officer: bool
    is_ten_percent_owner: bool
    officer_title: str | None = None
    transaction_date: datetime
    transaction_code: str
    transaction_type: TransactionType
    shares: float
    price_per_share: float | None = None
    transaction_value: float | None = None
    acquired_disposed: str
    shares_owned_after: float | None = None
    ownership_change_percent: float | None = None
    is_planned_sale: bool = False
    footnote_text: str | None = None
    filing_context: FilingContext | None = None
    filing_accession_number: str
    source_record_id: str
    synced_at: datetime


class AnomalyFeature(BaseModel):
    """PROMPT.md Phase 18 implement item 7: "deterministic anomaly
    features." No model call — a comparison against a stated, visible
    baseline, computed in code (CONSTITUTION.md: deterministic calculations
    belong in code). `baseline_description` exists specifically to satisfy
    verification 4 ("anomaly claims explain the comparison baseline") — an
    anomaly score with no visible baseline is not allowed to exist in this
    schema."""

    feature_name: str
    value: float
    baseline_description: str
    is_notable: bool


class InsiderProfile(BaseModel):
    """PROMPT.md Phase 18 implement item 6: "historical insider profile."
    A computed aggregate, not a persisted table — recomputed from the
    insider's own transaction history on every read, the same
    computed-not-stored pattern as Portfolio's `MoneyDashboard` (Phase 13),
    since it's a rolling view that changes as new transactions arrive, not
    a point-in-time fact worth its own immutable row."""

    insider_cik: str
    insider_name: str
    issuer_id: str
    transaction_count: int
    total_purchased_value: float
    total_sold_value: float
    average_transaction_shares: float
    first_transaction_date: datetime
    last_transaction_date: datetime


class InsiderEvidenceView(BaseModel):
    """PROMPT.md Phase 18 implement item 9: "evidence view" — mirrors
    `EvidencePackage` (Phase 16): every transaction, the computed profile,
    and every anomaly feature with its baseline, bundled together so a
    claim is never presented without the data it came from."""

    issuer_id: str
    insider_cik: str
    transactions: list[InsiderTransaction]
    profile: InsiderProfile | None
    anomalies: list[AnomalyFeature]
    generated_at: datetime
