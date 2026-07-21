"""Schwab adapter — plain httpx against Schwab's REST APIs, no third-party
SDK, matching the Ollama/Google Calendar adapters' precedent. Structurally
implements domains.portfolio.service.PortfolioProviderPort (a Protocol, so
no import of domains/ is needed here — scripts/check_architecture.py's
providers-must-not-import-domains rule) by returning Schwab's raw JSON as
plain dicts; translation into typed domain objects happens in
domains/portfolio/policies.py.

Endpoint URLs and OAuth mechanics were corroborated across multiple
independent real-integration sources before writing this file
(CONSTITUTION.md: Provider Due Diligence) — Schwab's own reference docs
require an authenticated developer login and could not be fetched directly.
Two real, non-obvious findings from that research:

1. Schwab has no separate read-only OAuth product — "Accounts and Trading
   Production" covers both reading positions and placing trades. There is
   no `scope` value that requests read-only access the way Google's
   `calendar.readonly` did. Read-only for this phase is enforced entirely
   by omission: no method here or in domains/portfolio/ ever calls a
   trading endpoint (PROMPT.md Phase 12 verification 5).
2. The registered redirect_uri (https://127.0.0.1:8182, fixed by the
   developer app's own registration, not reconfigurable per environment)
   is never actually reachable — nothing listens there. The user's browser
   lands on a dead page after consent and copies the resulting URL out of
   the address bar by hand (domains/portfolio/policies.py's
   `extract_code_from_redirect`) — there is no server-side callback to
   build, unlike Google Calendar's.

Token exchange uses HTTP Basic auth (client_id:client_secret) per Schwab's
own documented convention — client credentials do NOT go in the POST body
the way Google's OAuth token endpoint expects.
"""

from __future__ import annotations

import base64
import urllib.parse
from typing import Any

import httpx

from core.errors import ProviderUnavailableError

_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
# bandit misreads "token" in the URL path as a hardcoded credential — this is
# Schwab's published OAuth token endpoint, a public URL, not a secret.
_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"  # nosec B105
_ACCOUNT_NUMBERS_URL = "https://api.schwabapi.com/trader/v1/accounts/accountNumbers"
_ACCOUNTS_URL = "https://api.schwabapi.com/trader/v1/accounts"
_QUOTES_URL = "https://api.schwabapi.com/marketdata/v1/quotes"
_PRICE_HISTORY_URL = "https://api.schwabapi.com/marketdata/v1/pricehistory"


class SchwabAdapter:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "api",  # Schwab's own fixed literal — not a read/write choice
            "state": state,
        }
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        return await self._post_token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self._redirect_uri}
        )

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._post_token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    async def get_account_numbers(self, access_token: str) -> list[dict[str, Any]]:
        response = await self._get(_ACCOUNT_NUMBERS_URL, access_token)
        return response if isinstance(response, list) else []

    async def get_accounts(self, access_token: str) -> list[dict[str, Any]]:
        response = await self._get(_ACCOUNTS_URL, access_token, params={"fields": "positions"})
        return response if isinstance(response, list) else []

    async def get_quotes(self, access_token: str, symbols: list[str]) -> dict[str, Any]:
        return await self._get_dict(
            _QUOTES_URL, access_token, params={"symbols": ",".join(symbols)}
        )

    async def get_price_history(self, access_token: str, symbol: str) -> dict[str, Any]:
        return await self._get_dict(
            _PRICE_HISTORY_URL,
            access_token,
            params={
                "symbol": symbol,
                "periodType": "year",
                "period": 1,
                "frequencyType": "daily",
                "frequency": 1,
            },
        )

    def _auth_header(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def _get(
        self, url: str, access_token: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    url, params=params, headers=self._auth_header(access_token)
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Schwab request failed: {exc}") from exc

    async def _get_dict(
        self, url: str, access_token: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        result = await self._get(url, access_token, params=params)
        return result if isinstance(result, dict) else {}

    async def _post_token(self, data: dict[str, str]) -> dict[str, Any]:
        credentials = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode(
            "ascii"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    _TOKEN_URL,
                    data=data,
                    headers={
                        "Authorization": f"Basic {credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Schwab OAuth token request failed: {exc}") from exc
