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
