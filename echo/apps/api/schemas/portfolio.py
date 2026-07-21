"""API-boundary request/response schemas — never the domain's own
Account/Position/PortfolioSnapshot crossing the wire directly
(CONSTITUTION.md: Typed Contracts), matching apps/api/schemas/calendar.py's
convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
