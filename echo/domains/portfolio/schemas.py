"""Portfolio's own data contracts (Docs/DOMAIN_OWNERSHIP.md: Portfolio owns
Investment Accounts, Portfolio Positions, Portfolio Snapshots). Derived from
Docs/DATA_MODEL.md's Provenance Model and CONSTITUTION.md's Mandatory
Provider Normalization example (which names Schwab specifically: "Schwab
Position -> NormalizedPosition -> Portfolio Domain. The Portfolio Domain
shall never receive a Schwab SDK object.").
"""

from __future__ import annotations

from datetime import datetime

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
