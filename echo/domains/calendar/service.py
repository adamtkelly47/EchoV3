"""Calendar's aggregate-lifecycle owner. `CalendarProviderPort` is defined
here (not in providers/) matching domains/approvals/service.py's
`WriteAdapter` precedent: the domain owns the port, speaks to it in
primitives (raw dicts — Google's actual JSON responses), and does its own
translation into typed schemas (domains/calendar/policies.py) — so the
concrete provider adapter never needs to import anything from domains/
(scripts/check_architecture.py's providers-must-not-import-domains rule).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

from core.errors import EchoError
from core.identifiers import new_id
from core.time import Clock
from domains.calendar.errors import CalendarCredentialNotFoundError, CalendarTokenRefreshError
from domains.calendar.policies import (
    generate_oauth_state,
    is_stale,
    needs_refresh,
    parse_calendar_list,
    parse_event,
    parse_free_busy,
    verify_oauth_state,
)
from domains.calendar.repository import CalendarCredentialRepository, CalendarEventRepository
from domains.calendar.schemas import CalendarCredential, CalendarEvent, CalendarInfo, FreeBusyPeriod
from infrastructure.database.repositories.audit import AuditRepository
from infrastructure.secrets.encryption import SecretCipher

# How long a cached listing is trusted before a plain (non-search) read
# re-fetches from the provider (PROMPT.md Phase 10 implement items 9-10:
# calendar cache, freshness handling).
_CACHE_TTL = timedelta(minutes=5)


class CalendarProviderPort(Protocol):
    async def exchange_code(self, code: str) -> dict[str, Any]: ...
    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]: ...
    async def list_calendars(self, access_token: str) -> dict[str, Any]: ...
    async def list_events(
        self,
        access_token: str,
        *,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        query: str | None = None,
    ) -> list[dict[str, Any]]: ...
    async def get_event(
        self, access_token: str, *, calendar_id: str, event_id: str
    ) -> dict[str, Any]: ...
    async def free_busy(
        self, access_token: str, *, calendar_ids: list[str], time_min: datetime, time_max: datetime
    ) -> dict[str, Any]: ...
    def build_authorization_url(self, state: str) -> str: ...
    async def create_event(
        self, access_token: str, *, calendar_id: str, body: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def update_event(
        self, access_token: str, *, calendar_id: str, event_id: str, body: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def delete_event(self, access_token: str, *, calendar_id: str, event_id: str) -> None: ...


class CalendarService:
    def __init__(
        self,
        credentials: CalendarCredentialRepository,
        events: CalendarEventRepository,
        provider: CalendarProviderPort,
        cipher: SecretCipher,
        audit: AuditRepository,
        clock: Clock,
        state_secret: str,
    ) -> None:
        self._credentials = credentials
        self._events = events
        self._provider = provider
        self._cipher = cipher
        self._audit = audit
        self._clock = clock
        self._state_secret = state_secret

    def start_authorization(self, user_id: str) -> str:
        """Returns the full Google consent URL the user's browser should be
        sent to, embedding a signed, timestamped `state` (Docs/SECURITY.md:
        "Redirect target validation on OAuth callback flows")."""
        state = generate_oauth_state(user_id, new_id(), self._clock.now_utc(), self._state_secret)
        return self._provider.build_authorization_url(state)

    async def complete_authorization(self, code: str, state: str) -> CalendarCredential:
        """Verifies `state` before ever exchanging `code` — a forged or
        replayed callback never reaches Google's token endpoint."""
        user_id = verify_oauth_state(state, self._state_secret, self._clock.now_utc())
        return await self.connect(user_id, code)

    async def connect(self, user_id: str, code: str) -> CalendarCredential:
        """PROMPT.md Phase 10 implement items 1-3: OAuth, minimal read
        scopes (the scope actually granted comes back from Google itself,
        not assumed), token storage."""
        raw = await self._provider.exchange_code(code)
        now = self._clock.now_utc()
        credential = CalendarCredential(
            user_id=user_id,
            encrypted_access_token=self._cipher.encrypt(raw["access_token"]),
            encrypted_refresh_token=self._cipher.encrypt(raw["refresh_token"]),
            access_token_expires_at=now + timedelta(seconds=raw["expires_in"]),
            scope=raw.get("scope", ""),
            created_at=now,
            updated_at=now,
        )
        await self._credentials.save(credential)
        await self._audit.record(
            action="calendar.connected", result="success", detail={"user_id": user_id}
        )
        return credential

    async def is_connected(self, user_id: str) -> bool:
        """PROMPT.md Phase 22 implement item 6: "integration status." A
        credential existing is the real, honest signal available here —
        never a live provider health check on every dashboard load."""
        return await self._credentials.get_for_user(user_id) is not None

    async def list_calendars(self, user_id: str) -> list[CalendarInfo]:
        access_token = await self.get_valid_access_token(user_id)
        raw = await self._provider.list_calendars(access_token)
        return parse_calendar_list(raw)

    async def list_events(
        self,
        user_id: str,
        *,
        calendar_id: str = "primary",
        time_min: datetime,
        time_max: datetime,
        query: str | None = None,
        force_refresh: bool = False,
    ) -> list[CalendarEvent]:
        """Plain listing is cache-first (PROMPT.md Phase 10 implement items
        9-10). A text search always calls through — Google's own
        server-side relevance ranking for `q` can't be correctly
        reconstructed from a partial local cache."""
        if query is None and not force_refresh:
            cached = await self._events.list_in_range(user_id, calendar_id, time_min, time_max)
            if cached and not is_stale(
                min(e.synced_at for e in cached), self._clock.now_utc(), _CACHE_TTL
            ):
                return cached

        access_token = await self.get_valid_access_token(user_id)
        raw_events = await self._provider.list_events(
            access_token, calendar_id=calendar_id, time_min=time_min, time_max=time_max, query=query
        )
        synced_at = self._clock.now_utc()
        events = [
            parse_event(raw, user_id=user_id, calendar_id=calendar_id, synced_at=synced_at)
            for raw in raw_events
        ]
        if query is None:
            await self._events.upsert_many(events)
        return events

    async def get_event(
        self, user_id: str, *, calendar_id: str = "primary", event_id: str
    ) -> CalendarEvent:
        cached = await self._events.get(user_id, event_id)
        if cached is not None and not is_stale(cached.synced_at, self._clock.now_utc(), _CACHE_TTL):
            return cached

        access_token = await self.get_valid_access_token(user_id)
        raw = await self._provider.get_event(
            access_token, calendar_id=calendar_id, event_id=event_id
        )
        event = parse_event(
            raw, user_id=user_id, calendar_id=calendar_id, synced_at=self._clock.now_utc()
        )
        await self._events.upsert_many([event])
        return event

    async def free_busy(
        self, user_id: str, *, calendar_ids: list[str], time_min: datetime, time_max: datetime
    ) -> dict[str, list[FreeBusyPeriod]]:
        access_token = await self.get_valid_access_token(user_id)
        raw = await self._provider.free_busy(
            access_token, calendar_ids=calendar_ids, time_min=time_min, time_max=time_max
        )
        return {calendar_id: parse_free_busy(raw, calendar_id) for calendar_id in calendar_ids}

    async def cache_event(
        self, user_id: str, calendar_id: str, raw_event: dict[str, Any]
    ) -> CalendarEvent:
        """Phase 11: after a successful create/modify, the write path
        upserts the result into the same cache reads use, so a `list_events`
        immediately after doesn't need to wait out `_CACHE_TTL` to see it."""
        event = parse_event(
            raw_event, user_id=user_id, calendar_id=calendar_id, synced_at=self._clock.now_utc()
        )
        await self._events.upsert_many([event])
        return event

    async def evict_cached_event(self, user_id: str, provider_event_id: str) -> None:
        """Phase 11: after a successful delete, so a `list_events` doesn't
        keep showing an event Google itself no longer lists by default."""
        await self._events.delete(user_id, provider_event_id)

    async def get_valid_access_token(self, user_id: str) -> str:
        """Public (Phase 11): domains/calendar/write_adapters.py's
        WriteAdapter/ExecutionVerifier implementations need a valid token
        the same way every read method here does — refresh-if-needed stays
        centralized in one place rather than duplicated."""
        credential = await self._credentials.get_for_user(user_id)
        if credential is None:
            raise CalendarCredentialNotFoundError(f"no calendar connection for user {user_id!r}")

        now = self._clock.now_utc()
        if not needs_refresh(credential, now):
            return self._cipher.decrypt(credential.encrypted_access_token)

        refresh_token = self._cipher.decrypt(credential.encrypted_refresh_token)
        try:
            raw = await self._provider.refresh_access_token(refresh_token)
        except EchoError as exc:
            await self._audit.record(
                action="calendar.token_refresh_failed",
                result="failure",
                detail={"user_id": user_id},
            )
            raise CalendarTokenRefreshError(f"could not refresh calendar token: {exc}") from exc

        updated = credential.model_copy(
            update={
                "encrypted_access_token": self._cipher.encrypt(raw["access_token"]),
                "access_token_expires_at": now + timedelta(seconds=raw["expires_in"]),
                "updated_at": now,
            }
        )
        await self._credentials.save(updated)
        await self._audit.record(
            action="calendar.token_refreshed", result="success", detail={"user_id": user_id}
        )
        return self._cipher.decrypt(updated.encrypted_access_token)
