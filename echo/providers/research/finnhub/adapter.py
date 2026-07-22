"""Finnhub adapter — plain httpx, no third-party SDK, matching the Schwab/
Google Calendar adapters' precedent. Structurally implements
domains.research.service.ResearchProviderPort (a Protocol, so no import of
domains/ is needed here — scripts/check_architecture.py's
providers-must-not-import-domains rule) by returning Finnhub's raw JSON as a
plain dict; translation into typed domain objects happens in
domains/research/policies.py.

Live-verified working for company profile and company news data in Phase 15
(Docs/DECISION_LOG.md's Phase 15 entry: 23/28 criteria passed for
fundamentals/earnings/analyst_ratings/company_news on the free tier).
`market_history` (the `/stock/candle` endpoint) is paywalled on this tier —
not used here. `get_company_news` structurally implements
domains.research.service.NewsProviderPort (PROMPT.md Phase 17) the same way
`get_issuer_profile` implements `ResearchProviderPort` — Python's structural
typing means one adapter class can satisfy more than one Protocol without
declaring either explicitly.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.errors import ProviderUnavailableError

_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubAdapter:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_issuer_profile(self, ticker: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{_BASE_URL}/stock/profile2",
                    params={"symbol": ticker, "token": self._api_key},
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Finnhub request failed: {exc}") from exc

    async def get_company_news(
        self, ticker: str, *, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{_BASE_URL}/company-news",
                    params={
                        "symbol": ticker,
                        "from": from_date,
                        "to": to_date,
                        "token": self._api_key,
                    },
                )
                response.raise_for_status()
                body = response.json()
                return body if isinstance(body, list) else []
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Finnhub news request failed: {exc}") from exc
