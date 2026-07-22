"""Portfolio's own vocabulary, kept independent of any single provider's raw
strings (Docs/DOMAIN_OWNERSHIP.md: Portfolio's external providers include
Schwab, Fidelity, Interactive Brokers, JP Morgan, Vanguard, CSV Import —
"Providers normalize data. Portfolio owns meaning."). Schwab's raw
`assetType` values are translated into this by domains/portfolio/policies.py.
"""

from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    OPTION = "option"
    MUTUAL_FUND = "mutual_fund"
    FIXED_INCOME = "fixed_income"
    CASH_EQUIVALENT = "cash_equivalent"
    OTHER = "other"


class HypotheticalTradeAction(str, Enum):
    """PROMPT.md Phase 27: "paper trading observation." Only a directional
    stance, never a real order — there is deliberately no quantity-only
    "trade" concept that could later grow an execute() method; the whole
    point of this vocabulary is that it can never mean anything but a
    recorded thesis about a direction."""

    BUY = "buy"
    SELL = "sell"


class HypotheticalTradeStatus(str, Enum):
    """PROMPT.md Phase 27 capability 8: "review failures." OPEN is the only
    state a proposal starts in; CLOSED is reached only through an explicit,
    human-authored review — mirroring `domains/system/models.py`'s
    `HallucinationIncidentStatus` precedent (a report exists, then is later
    reviewed; no re-opening concept)."""

    OPEN = "open"
    CLOSED = "closed"
