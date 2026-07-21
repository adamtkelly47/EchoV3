"""Thin, generic HTTP fetch used by every candidate provider in this
evaluation harness. Deliberately not `providers/<name>/adapter.py` — those
exist only for a provider a domain has actually adopted (PROMPT.md Phase 15:
"Do not select a permanent provider before this phase"). No response
shaping happens here; `runner.py` interprets the raw bytes/status/timing
into `metrics.ProviderTestResult`s, so a paywalled or malformed response is
recorded as real evidence, never silently normalized away.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

FINNHUB_BASE = "https://finnhub.io/api/v1"
FMP_BASE_V3 = "https://financialmodelingprep.com/api/v3"
FMP_BASE_V4 = "https://financialmodelingprep.com/api/v4"
SEC_EDGAR_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SENATE_STOCK_WATCHER_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
)
HOUSE_STOCK_WATCHER_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions_qs.json"
)
REDDIT_SEARCH_URL = "https://www.reddit.com/r/wallstreetbets/search.json"


@dataclass(frozen=True)
class RawResponse:
    status_code: int
    elapsed_ms: float
    json_body: Any | None
    text_excerpt: str
    headers: dict[str, str]
    error: str | None = None


async def fetch(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> RawResponse:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return RawResponse(
            status_code=0,
            elapsed_ms=elapsed_ms,
            json_body=None,
            text_excerpt="",
            headers={},
            error=str(exc),
        )
    elapsed_ms = (time.monotonic() - start) * 1000
    try:
        body = response.json()
    except ValueError:
        body = None
    return RawResponse(
        status_code=response.status_code,
        elapsed_ms=elapsed_ms,
        json_body=body,
        text_excerpt=response.text[:500],
        headers=dict(response.headers),
    )


def finnhub_url(path: str, api_key: str, **params: Any) -> tuple[str, dict[str, Any]]:
    query = {**params, "token": api_key}
    return f"{FINNHUB_BASE}{path}", query


def fmp_v3_url(path: str, api_key: str, **params: Any) -> tuple[str, dict[str, Any]]:
    query = {**params, "apikey": api_key}
    return f"{FMP_BASE_V3}{path}", query


def fmp_v4_url(path: str, api_key: str, **params: Any) -> tuple[str, dict[str, Any]]:
    query = {**params, "apikey": api_key}
    return f"{FMP_BASE_V4}{path}", query


def sec_edgar_headers(contact_email: str) -> dict[str, str]:
    """SEC's fair-access policy requires a descriptive User-Agent with a
    real, reachable contact — an anonymous or browser-spoofed User-Agent is
    documented to get throttled or rejected. Not committed to source: the
    real address is only ever read from Settings (core/config/settings.py),
    same as every other credential in this codebase."""
    return {"User-Agent": f"Echo Personal AI Operating System (evaluation harness) {contact_email}"}


def reddit_headers() -> dict[str, str]:
    """Reddit's public JSON endpoints reject the default httpx User-Agent
    outright — a descriptive one is the minimum needed to even get past that,
    not a guarantee of success (Reddit's real API requires OAuth registration
    for sustained use; this tests only the unauthenticated public path)."""
    return {"User-Agent": "echo-provider-evaluation/1.0 (by /u/research)"}
