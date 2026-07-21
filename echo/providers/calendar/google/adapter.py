"""Google Calendar adapter — plain httpx against Google's REST APIs, no
google-api-python-client/google-auth SDK dependency, matching the Ollama
adapter's precedent (providers/models/ollama/adapter.py) of talking to a
vendor's HTTP API directly rather than adding an SDK. Structurally
implements domains.calendar.service.CalendarProviderPort (a Protocol, so no
import of domains/ is needed here — scripts/check_architecture.py's
providers-must-not-import-domains rule) by returning Google's raw JSON as
plain dicts; translation into typed domain objects happens in
domains/calendar/policies.py.

Endpoint URLs, request parameters, and response shapes were verified live
against Google's own current API documentation before writing this file
(CONSTITUTION.md: Provider Due Diligence — "Marketing material shall not be
treated as authoritative technical documentation," and more specifically,
nothing here is guessed from training data):
- OAuth: https://developers.google.com/identity/protocols/oauth2/web-server
- Events: https://developers.google.com/calendar/api/v3/reference/events(/list)
- CalendarList: https://developers.google.com/calendar/api/v3/reference/calendarList/list
- FreeBusy: https://developers.google.com/calendar/api/v3/reference/freebusy/query
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Any

import httpx

from core.errors import ProviderUnavailableError

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# bandit misreads "token" in the URL path as a hardcoded credential — this is
# Google's published OAuth token endpoint, a public URL, not a secret.
_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105
_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
_EVENTS_BASE_URL = "https://www.googleapis.com/calendar/v3/calendars"
_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"

# Docs/SECURITY.md: "Read integrations ... request read-only scopes; write
# scopes are never requested until the corresponding write phase ... is
# reached" — Calendar's write phase (11) does not exist yet.
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class GoogleCalendarAdapter:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": READ_ONLY_SCOPE,
            "access_type": "offline",  # required to receive a refresh_token
            "prompt": "consent",  # guarantees a refresh_token even on re-auth
            "state": state,
        }
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        return await self._post_form(
            _TOKEN_URL,
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._post_form(
            _TOKEN_URL,
            {
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            },
        )

    async def list_calendars(self, access_token: str) -> dict[str, Any]:
        return await self._get(_CALENDAR_LIST_URL, access_token)

    async def list_events(
        self,
        access_token: str,
        *,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",  # expands recurring events into instances
            "orderBy": "startTime",
            "maxResults": 250,
        }
        if query:
            params["q"] = query
        url = f"{_EVENTS_BASE_URL}/{urllib.parse.quote(calendar_id, safe='')}/events"
        response = await self._get(url, access_token, params=params)
        items: list[dict[str, Any]] = response.get("items", [])
        return items

    async def get_event(
        self, access_token: str, *, calendar_id: str, event_id: str
    ) -> dict[str, Any]:
        url = (
            f"{_EVENTS_BASE_URL}/{urllib.parse.quote(calendar_id, safe='')}"
            f"/events/{urllib.parse.quote(event_id, safe='')}"
        )
        return await self._get(url, access_token)

    async def free_busy(
        self, access_token: str, *, calendar_ids: list[str], time_min: datetime, time_max: datetime
    ) -> dict[str, Any]:
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": calendar_id} for calendar_id in calendar_ids],
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    _FREEBUSY_URL, json=body, headers=self._auth_header(access_token)
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Google Calendar freeBusy request failed: {exc}"
            ) from exc

    def _auth_header(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def _get(
        self, url: str, access_token: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    url, params=params, headers=self._auth_header(access_token)
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Google Calendar request failed: {exc}") from exc

    async def _post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Google OAuth token request failed: {exc}") from exc
