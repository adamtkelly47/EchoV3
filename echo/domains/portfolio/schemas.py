"""Portfolio's own data contracts (Docs/DOMAIN_OWNERSHIP.md: Portfolio owns
Investment Accounts, Portfolio Positions, Portfolio Snapshots). Derived from
Docs/DATA_MODEL.md's Provenance Model and CONSTITUTION.md's Mandatory
Provider Normalization example (which names Schwab specifically: "Schwab
Position -> NormalizedPosition -> Portfolio Domain. The Portfolio Domain
shall never receive a Schwab SDK object.").
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.portfolio.models import AssetType


class SchwabCredential(BaseModel):
    """Unlike Google's refresh tokens (Docs/DECISION_LOG.md's Phase 10
    entry), Schwab's refresh token itself expires — after a hard 7-day
    limit, with no programmatic renewal (verified against Schwab's own
    documented token lifetimes, not assumed). `refresh_token_expires_at`
    lets domains/portfolio/policies.py detect this and fail with a distinct,
    honest "reconnect required" error rather than a generic refresh
    failure."""

    credential_id: str = Field(default_factory=lambda: new_id("schwabcred"))
    user_id: str
    encrypted_access_token: str
    encrypted_refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    created_at: datetime
    updated_at: datetime


class Account(BaseModel):
    account_id: str = Field(default_factory=lambda: new_id("account"))
    user_id: str
    # Schwab's own opaque per-account hash — used for every subsequent API
    # call. The real account number is never persisted (PROMPT.md Phase 12
    # implement item 4 / verification item 6) — only its last 4 digits,
    # via `display_mask`, computed once at discovery time.
    account_hash: str
    display_mask: str
    account_type: str
    synced_at: datetime


class Position(BaseModel):
    position_id: str = Field(default_factory=lambda: new_id("position"))
    account_id: str
    user_id: str
    symbol: str
    asset_type: AssetType
    quantity: float
    # Missing stays missing (PROMPT.md Phase 12 verification 3) — never
    # estimated to "fill in" a gain/loss calculation (Docs/DATA_MODEL.md:
    # Negative and Missing Data).
    average_price: float | None = None
    market_value: float | None = None
    current_price: float | None = None
    day_change_dollar: float | None = None
    day_change_percent: float | None = None
    source_record_id: str
    synced_at: datetime


class AccountBalance(BaseModel):
    balance_id: str = Field(default_factory=lambda: new_id("balance"))
    account_id: str
    user_id: str
    cash_balance: float | None = None
    # Schwab's own reported total — kept separate from our own computed
    # total so domains/portfolio/policies.py's reconciliation check has
    # something independent to compare against.
    schwab_reported_total: float | None = None
    source_record_id: str
    synced_at: datetime


class PortfolioSnapshot(BaseModel):
    """Immutable point-in-time capture (CONSTITUTION.md: Aggregate
    Ownership — "PortfolioSnapshot owns: immutability / timestamp
    consistency / provenance linkage"). Never updated after creation — a
    new sync creates a new snapshot (Docs/DATA_MODEL.md: Immutability)."""

    snapshot_id: str = Field(default_factory=lambda: new_id("snapshot"))
    user_id: str
    taken_at: datetime
    total_market_value: float
    reconciled: bool
    reconciliation_diff: float | None = None
    account_ids: list[str]
    # PROMPT.md Phase 12 verification 4: "partial API responses produce
    # visible warnings" — e.g. an account whose positions call failed is
    # recorded here, not silently dropped from the snapshot.
    warnings: list[str] = Field(default_factory=list)


class Quote(BaseModel):
    """Real-time quotes are not persisted as their own aggregate — unlike
    positions, which are meaningfully snapshotted, a quote is stale the
    instant it's read. Provenance (`source_record_id`) still applies."""

    symbol: str
    price: float | None = None
    change_dollar: float | None = None
    change_percent: float | None = None
    retrieved_at: datetime
    source_record_id: str


class PriceHistoryPoint(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class PositionWeight(BaseModel):
    symbol: str
    account_id: str
    market_value: float
    weight_percent: float


class AssetClassExposure(BaseModel):
    asset_type: AssetType
    market_value: float
    weight_percent: float


class SectorExposure(BaseModel):
    """`sector` is always "Unknown" until a real sector data source exists.
    Docs/DOMAIN_OWNERSHIP.md assigns "Company fundamentals" (which sector
    classification is part of) to the Research domain, not Portfolio, and
    Research isn't built until PROMPT.md Phase 16 — so this is deliberately
    a single "Unknown" bucket for now rather than a fabricated mapping
    (CONSTITUTION.md: Verified Truth)."""

    sector: str
    market_value: float
    weight_percent: float


class SymbolExposure(BaseModel):
    """Cross-account exposure: the same symbol held in more than one
    account, aggregated (PROMPT.md Phase 13 implement item 3)."""

    symbol: str
    total_quantity: float
    total_market_value: float
    account_ids: list[str]


class ConcentrationWarning(BaseModel):
    symbol: str
    weight_percent: float
    threshold_percent: float


class PositionGainLoss(BaseModel):
    """`cost_basis`/`unrealized_gain_loss_*` stay `None` when Schwab never
    reported `average_price` for this position — never estimated to "fill
    in" a gain/loss figure (PROMPT.md Phase 13 verification item 4)."""

    symbol: str
    account_id: str
    quantity: float
    cost_basis: float | None
    market_value: float | None
    unrealized_gain_loss_dollar: float | None
    unrealized_gain_loss_percent: float | None


class MoneyDashboard(BaseModel):
    """PROMPT.md Phase 13 implement item 10 / Section 22.2 ("Money" section
    of the eventual unified dashboard, Phase 22). Built entirely from the
    latest already-synced, reconciled snapshot — never triggers a live
    Schwab call (deterministic analysis of verified data, not a fresh
    read)."""

    user_id: str
    generated_at: datetime
    last_verified_sync_at: datetime
    is_stale: bool
    total_market_value: float
    reconciled: bool
    position_weights: list[PositionWeight]
    asset_class_exposure: list[AssetClassExposure]
    sector_exposure: list[SectorExposure]
    cross_account_exposure: list[SymbolExposure]
    concentration_warnings: list[ConcentrationWarning]
    unrealized_gain_loss: list[PositionGainLoss]
    total_unrealized_gain_loss_dollar: float | None
    warnings: list[str] = Field(default_factory=list)
    computed_value_record_id: str


class AllocationRange(BaseModel):
    asset_type: AssetType
    min_percent: float = Field(ge=0, le=100)
    max_percent: float = Field(ge=0, le=100)


class ConcentrationRule(BaseModel):
    """Generalizes Phase 13's hardcoded `_DEFAULT_CONCENTRATION_THRESHOLD_PERCENT`
    into a real, user-authored rule (Docs/DECISION_LOG.md's Phase 13 entry
    said as much: "used until an Investment Policy Statement ... can supply
    a user-specific one")."""

    max_position_percent: float = Field(gt=0, le=100)


class RestrictedSecurity(BaseModel):
    symbol: str
    reason: str | None = None


class IPSVersion(BaseModel):
    """A written, versioned strategy constraint document (PROMPT.md Phase 14).
    Immutable once created (Docs/DATA_MODEL.md: Immutability, same pattern
    as PortfolioSnapshot) — editing an IPS never mutates a prior version's
    rules, it supersedes it with a new one (verification 3: "updating an IPS
    does not rewrite historical evaluations"). `ips_id` is stable across a
    user's versions; `version_number` increments; `is_active` marks the
    single current version driving new compliance evaluations."""

    version_id: str = Field(default_factory=lambda: new_id("ipsver"))
    ips_id: str
    version_number: int
    user_id: str
    # Empty means "applies to every account" — a real, explicit choice, not
    # an accidental omission (PROMPT.md Phase 14 implement item 4).
    account_ids: list[str] = Field(default_factory=list)
    allocation_ranges: list[AllocationRange] = Field(default_factory=list)
    concentration_rule: ConcentrationRule
    restricted_securities: list[RestrictedSecurity] = Field(default_factory=list)
    created_at: datetime
    is_active: bool


class ComplianceBreach(BaseModel):
    rule_type: str
    description: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ComplianceResult(BaseModel):
    """Immutable evaluation record (PROMPT.md Phase 14 verification 2/3):
    cites both the exact `ips_version_id` and `snapshot_id` it was evaluated
    against, so a later IPS edit or portfolio sync can never retroactively
    change what this result says. `domains/portfolio/policies.py`'s
    `evaluate_compliance` is the only thing that produces `breaches` — it is
    a pure function with no I/O (verification 1: "IPS rules are
    deterministic")."""

    result_id: str = Field(default_factory=lambda: new_id("compliance"))
    user_id: str
    ips_version_id: str
    snapshot_id: str
    evaluated_at: datetime
    compliant: bool
    breaches: list[ComplianceBreach] = Field(default_factory=list)
