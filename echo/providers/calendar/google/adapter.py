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
- Events: https://developers.google.com/calendar/api/v3/reference/events(/list/insert/patch/delete)
- CalendarList: https://developers.google.com/calendar/api/v3/reference/calendarList/list
- FreeBusy: https://developers.google.com/calendar/api/v3/reference/freebusy/query
- Recurring event edit scope: https://developers.google.com/calendar/api/guides/recurringevents
  (verified live: the API natively supports exactly two scopes — PATCH/DELETE
  a single instance's own event id, or PATCH/DELETE the parent recurring
  event's id for the whole series. "This and following" is NOT a native
  scope; Google's own guide describes it as a two-call workaround — truncate
  the original series' RRULE with UNTIL, then insert a new series — which
  this phase deliberately does not implement (PROMPT.md Phase 11: "narrow,
  safe calendar modifications"; a 2-call, partially-completable operation is
  neither).
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
# reached" — Phase 11 is that write phase. `calendar.events` ("View and edit
# events on all your calendars", verified against Google's own scope list)
# is added alongside the existing calendar.readonly rather than replacing
# it — Phase 10's calendarList.list read isn't documented as covered by
# calendar.events alone, and the much broader `calendar` scope (which also
# permits deleting entire calendars) is more than event create/modify/
# delete needs (CONSTITUTION.md: Least Privilege). A user who authorized
# under the old read-only-only grant must re-authorize — Google does not
# retroactively upgrade an existing grant's scope.
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"
_REQUESTED_SCOPE = f"{READ_ONLY_SCOPE} {WRITE_SCOPE}"


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
            "scope": _REQUESTED_SCOPE,
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
        url = self._event_url(calendar_id, event_id)
        return await self._get(url, access_token)

    async def create_event(
        self, access_token: str, *, calendar_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{_EVENTS_BASE_URL}/{urllib.parse.quote(calendar_id, safe='')}/events"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url, json=body, headers=self._auth_header(access_token)
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Google Calendar create-event request failed: {exc}"
            ) from exc

    async def update_event(
        self, access_token: str, *, calendar_id: str, event_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH, not PUT — partial update semantics, so only the fields
        actually being changed need to be present in `body` (Google's own
        PATCH semantics, verified live)."""
        url = self._event_url(calendar_id, event_id)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.patch(
                    url, json=body, headers=self._auth_header(access_token)
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Google Calendar update-event request failed: {exc}"
            ) from exc

    async def delete_event(self, access_token: str, *, calendar_id: str, event_id: str) -> None:
        url = self._event_url(calendar_id, event_id)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(url, headers=self._auth_header(access_token))
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Google Calendar delete-event request failed: {exc}"
            ) from exc

    def _event_url(self, calendar_id: str, event_id: str) -> str:
        return (
            f"{_EVENTS_BASE_URL}/{urllib.parse.quote(calendar_id, safe='')}"
            f"/events/{urllib.parse.quote(event_id, safe='')}"
        )

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
