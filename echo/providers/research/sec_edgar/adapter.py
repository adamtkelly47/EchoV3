"""SEC EDGAR adapter — plain httpx against SEC's public REST API, no
third-party SDK. Keyless, but SEC's fair-access policy requires a
descriptive User-Agent with a real, reachable contact address — live-
verified working in Phase 15 (Docs/DECISION_LOG.md's Phase 15 entry: 6/7
criteria passed, real Form 4 and filing-history data confirmed for AAPL).

No ticker-based lookup endpoint exists — a ticker must be resolved to a CIK
via the separate `company_tickers.json` map first, then the submissions
endpoint queried by that CIK. Both steps live inside `get_issuer_profile` so
domains/research/service.py's `ResearchProviderPort` Protocol stays a single
method, matching every other provider adapter in this codebase.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.errors import ProviderUnavailableError

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


class SecEdgarAdapter:
    def __init__(self, contact_email: str) -> None:
        self._headers = {
            "User-Agent": f"Echo Personal AI Operating System (research domain) {contact_email}"
        }

    async def get_issuer_profile(self, ticker: str) -> dict[str, Any]:
        cik = await self._resolve_cik(ticker)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_SUBMISSIONS_URL.format(cik=cik), headers=self._headers)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"SEC EDGAR submissions request failed: {exc}") from exc

    async def _resolve_cik(self, ticker: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_TICKER_MAP_URL, headers=self._headers)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"SEC EDGAR ticker map request failed: {exc}") from exc
        for entry in body.values():
            if isinstance(entry, dict) and entry.get("ticker") == ticker:
                return str(entry["cik_str"]).zfill(10)
        raise ProviderUnavailableError(f"SEC EDGAR: no CIK found for ticker {ticker!r}")
