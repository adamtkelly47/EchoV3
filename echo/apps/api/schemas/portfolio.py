"""API-boundary request/response schemas — never the domain's own
Account/Position/PortfolioSnapshot crossing the wire directly
(CONSTITUTION.md: Typed Contracts), matching apps/api/schemas/calendar.py's
convention.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompleteAuthorizationRequest(BaseModel):
    """The user pastes the full dead-page URL their browser landed on after
    Schwab consent (or just the extracted `code`) — Schwab's fixed
    127.0.0.1 callback is never actually reachable by a server
    (Docs/DECISION_LOG.md's Phase 12 entry)."""

    state: str
    redirect_value: str


class ConnectResponse(BaseModel):
    user_id: str
    connected: bool


class AccountResponse(BaseModel):
    account_id: str
    account_hash: str
    display_mask: str
    account_type: str
    synced_at: datetime


class AccountListResponse(BaseModel):
    accounts: list[AccountResponse]


class SnapshotResponse(BaseModel):
    snapshot_id: str
    user_id: str
    taken_at: datetime
    total_market_value: float
    reconciled: bool
    reconciliation_diff: float | None
    account_ids: list[str]
    warnings: list[str]


class QuoteResponse(BaseModel):
    symbol: str
    price: float | None
    change_dollar: float | None
    change_percent: float | None
    retrieved_at: datetime


class QuoteListResponse(BaseModel):
    quotes: list[QuoteResponse]


class PriceHistoryPointResponse(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistoryResponse(BaseModel):
    symbol: str
    points: list[PriceHistoryPointResponse]


class PositionWeightResponse(BaseModel):
    symbol: str
    account_id: str
    market_value: float
    weight_percent: float


class AssetClassExposureResponse(BaseModel):
    asset_type: str
    market_value: float
    weight_percent: float


class SectorExposureResponse(BaseModel):
    sector: str
    market_value: float
    weight_percent: float


class SymbolExposureResponse(BaseModel):
    symbol: str
    total_quantity: float
    total_market_value: float
    account_ids: list[str]


class ConcentrationWarningResponse(BaseModel):
    symbol: str
    weight_percent: float
    threshold_percent: float


class PositionGainLossResponse(BaseModel):
    symbol: str
    account_id: str
    quantity: float
    cost_basis: float | None
    market_value: float | None
    unrealized_gain_loss_dollar: float | None
    unrealized_gain_loss_percent: float | None


class MoneyDashboardResponse(BaseModel):
    user_id: str
    generated_at: datetime
    last_verified_sync_at: datetime
    is_stale: bool
    total_market_value: float
    reconciled: bool
    position_weights: list[PositionWeightResponse]
    asset_class_exposure: list[AssetClassExposureResponse]
    sector_exposure: list[SectorExposureResponse]
    cross_account_exposure: list[SymbolExposureResponse]
    concentration_warnings: list[ConcentrationWarningResponse]
    unrealized_gain_loss: list[PositionGainLossResponse]
    total_unrealized_gain_loss_dollar: float | None
    warnings: list[str]
    computed_value_record_id: str


class AllocationRangeRequest(BaseModel):
    asset_type: str
    min_percent: float
    max_percent: float


class RestrictedSecurityRequest(BaseModel):
    symbol: str
    reason: str | None = None


class CreateIPSVersionRequest(BaseModel):
    """`ips_id=None` starts a brand-new IPS document; an existing `ips_id`
    supersedes its current active version with a new one (PROMPT.md Phase 14
    implement item 3: "versioning")."""

    ips_id: str | None = None
    account_ids: list[str] = Field(default_factory=list)
    allocation_ranges: list[AllocationRangeRequest] = Field(default_factory=list)
    max_position_percent: float
    restricted_securities: list[RestrictedSecurityRequest] = Field(default_factory=list)


class AllocationRangeResponse(BaseModel):
    asset_type: str
    min_percent: float
    max_percent: float


class RestrictedSecurityResponse(BaseModel):
    symbol: str
    reason: str | None


class IPSVersionResponse(BaseModel):
    version_id: str
    ips_id: str
    version_number: int
    user_id: str
    account_ids: list[str]
    allocation_ranges: list[AllocationRangeResponse]
    max_position_percent: float
    restricted_securities: list[RestrictedSecurityResponse]
    created_at: datetime
    is_active: bool


class IPSVersionListResponse(BaseModel):
    versions: list[IPSVersionResponse]


class ComplianceBreachResponse(BaseModel):
    rule_type: str
    description: str
    detail: dict[str, Any]


class ComplianceResultResponse(BaseModel):
    result_id: str
    user_id: str
    ips_version_id: str
    snapshot_id: str
    evaluated_at: datetime
    compliant: bool
    breaches: list[ComplianceBreachResponse]
