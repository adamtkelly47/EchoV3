from __future__ import annotations

from datetime import datetime
from typing import Any

from domains.calendar.schemas import CalendarCredential, CalendarEvent


class FakeCalendarCredentialRepository:
    def __init__(self) -> None:
        self._store: dict[str, CalendarCredential] = {}

    async def save(self, credential: CalendarCredential) -> None:
        self._store[credential.user_id] = credential

    async def get_for_user(self, user_id: str) -> CalendarCredential | None:
        return self._store.get(user_id)


class FakeCalendarEventRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], CalendarEvent] = {}

    async def upsert_many(self, events: list[CalendarEvent]) -> None:
        for event in events:
            self._by_key[(event.user_id, event.provider_event_id)] = event

    async def list_in_range(
        self, user_id: str, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[CalendarEvent]:
        return [
            e
            for e in self._by_key.values()
            if e.user_id == user_id
            and e.calendar_id == calendar_id
            and e.start < time_max
            and e.end > time_min
        ]

    async def get(self, user_id: str, provider_event_id: str) -> CalendarEvent | None:
        return self._by_key.get((user_id, provider_event_id))

    async def delete(self, user_id: str, provider_event_id: str) -> None:
        self._by_key.pop((user_id, provider_event_id), None)


class FakeCalendarProvider:
    """Configurable stand-in for CalendarProviderPort. Every method's
    response is set directly on the instance before use; `calls` records
    the method name and kwargs so tests can assert what was actually
    requested (e.g. that a token refresh was or wasn't triggered)."""

    def __init__(self) -> None:
        self.token_response: dict[str, Any] = {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/calendar.readonly",
        }
        self.refresh_response: dict[str, Any] = {
            "access_token": "fake-refreshed-token",
            "expires_in": 3600,
        }
        self.calendar_list_response: dict[str, Any] = {"items": []}
        self.events_response: list[dict[str, Any]] = []
        self.get_event_response: dict[str, Any] = {}
        self.free_busy_response: dict[str, Any] = {"calendars": {}}
        self.create_event_response: dict[str, Any] = {
            "id": "created-event-id",
            "summary": "Created",
        }
        self.update_event_response: dict[str, Any] = {
            "id": "existing-event-id",
            "summary": "Updated",
        }
        self.raise_on_refresh: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def build_authorization_url(self, state: str) -> str:
        self.calls.append(("build_authorization_url", {"state": state}))
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        self.calls.append(("exchange_code", {"code": code}))
        return self.token_response

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        self.calls.append(("refresh_access_token", {"refresh_token": refresh_token}))
        if self.raise_on_refresh:
            raise self.raise_on_refresh
        return self.refresh_response

    async def list_calendars(self, access_token: str) -> dict[str, Any]:
        self.calls.append(("list_calendars", {"access_token": access_token}))
        return self.calendar_list_response

    async def list_events(
        self,
        access_token: str,
        *,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "list_events",
                {
                    "access_token": access_token,
                    "calendar_id": calendar_id,
                    "time_min": time_min,
                    "time_max": time_max,
                    "query": query,
                },
            )
        )
        return self.events_response

    async def get_event(
        self, access_token: str, *, calendar_id: str, event_id: str
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_event",
                {"access_token": access_token, "calendar_id": calendar_id, "event_id": event_id},
            )
        )
        return self.get_event_response

    async def free_busy(
        self, access_token: str, *, calendar_ids: list[str], time_min: datetime, time_max: datetime
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "free_busy",
                {
                    "access_token": access_token,
                    "calendar_ids": calendar_ids,
                    "time_min": time_min,
                    "time_max": time_max,
                },
            )
        )
        return self.free_busy_response

    async def create_event(
        self, access_token: str, *, calendar_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "create_event",
                {"access_token": access_token, "calendar_id": calendar_id, "body": body},
            )
        )
        return self.create_event_response

    async def update_event(
        self, access_token: str, *, calendar_id: str, event_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "update_event",
                {
                    "access_token": access_token,
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                    "body": body,
                },
            )
        )
        return self.update_event_response

    async def delete_event(self, access_token: str, *, calendar_id: str, event_id: str) -> None:
        self.calls.append(
            (
                "delete_event",
                {"access_token": access_token, "calendar_id": calendar_id, "event_id": event_id},
            )
        )


class FakeAuditRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        call_id = f"audit_fake_{len(self.recorded)}"
        self.recorded.append(
            {"audit_id": call_id, "action": action, "result": result, "detail": detail}
        )
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e.get("correlation_id") == correlation_id]
