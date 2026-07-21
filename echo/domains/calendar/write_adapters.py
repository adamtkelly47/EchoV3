"""Concrete `WriteAdapter`/`ExecutionVerifier` implementations
(domains/approvals/service.py's Protocols) for Calendar writes. Constructed
per-request by application/orchestrators/calendar_writes.py with one
specific user's already-resolved access token — never shared across users
or cached (PROMPT.md Phase 11 implement items 2/3/5/7: execution and
post-execution verification for create/modify/delete).

Payload shape (Docs/DECISION_LOG.md's Phase 11 entry documents this
convention): every proposal's `payload` dict always has `action` and
`calendar_id`. `create_event` additionally has `summary`/`start`/`end`
(Google's own nested `{"date": ...}`/`{"dateTime": ..., "timeZone": ...}`
shape, built once by the orchestrator so this module never has to know
about datetimes) and optional `description`. `modify_event`/`delete_event`
additionally have `provider_event_id`, `recurring_event_id` (or `None`),
and `scope` (a domains.calendar.models.RecurringEditScope value) — the
target event id to act on is `recurring_event_id` for
`RecurringEditScope.ENTIRE_SERIES`, `provider_event_id` otherwise.
"""

from __future__ import annotations

from typing import Any

from core.errors import EchoError
from domains.calendar.models import RecurringEditScope
from domains.calendar.service import CalendarProviderPort


def target_event_id(payload: dict[str, Any]) -> str:
    scope = RecurringEditScope(payload["scope"])
    if scope is RecurringEditScope.ENTIRE_SERIES:
        recurring_event_id = payload.get("recurring_event_id")
        if not recurring_event_id:
            raise ValueError("scope is entire_series but payload has no recurring_event_id")
        return str(recurring_event_id)
    return str(payload["provider_event_id"])


def _event_body(payload: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for field in ("summary", "description", "start", "end"):
        if field in payload:
            body[field] = payload[field]
    return body


class CalendarCreateEventWriteAdapter:
    def __init__(self, provider: CalendarProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.create_event(
            self._access_token, calendar_id=payload["calendar_id"], body=_event_body(payload)
        )


class CalendarModifyEventWriteAdapter:
    def __init__(self, provider: CalendarProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.update_event(
            self._access_token,
            calendar_id=payload["calendar_id"],
            event_id=target_event_id(payload),
            body=_event_body(payload),
        )


class CalendarDeleteEventWriteAdapter:
    def __init__(self, provider: CalendarProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = target_event_id(payload)
        await self._provider.delete_event(
            self._access_token, calendar_id=payload["calendar_id"], event_id=event_id
        )
        # ApprovalService's WriteAdapter.execute must return a dict (the
        # execution result an ExecutionVerifier inspects) — delete has no
        # natural response body, so this synthesizes the one fact that
        # matters: which event was targeted.
        return {"id": event_id}


class CalendarWriteVerifier:
    """PROMPT.md Phase 11 verification 4: "External result is reloaded and
    verified" — re-fetches the event from Google (a fresh, independent read,
    not just trusting the write response) rather than assuming success."""

    def __init__(self, provider: CalendarProviderPort, access_token: str, calendar_id: str) -> None:
        self._provider = provider
        self._access_token = access_token
        self._calendar_id = calendar_id

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        event_id = execution_result.get("id")
        if not event_id:
            return False
        try:
            reloaded = await self._provider.get_event(
                self._access_token, calendar_id=self._calendar_id, event_id=event_id
            )
        except EchoError:
            return False
        return bool(reloaded.get("id") == event_id)


class CalendarDeleteVerifier:
    """A deleted event is not removed outright — Google marks it
    `status: "cancelled"` and still returns it from a GET (verified live
    against Google's own documented behavior, not assumed) — so success
    here means "reloads with cancelled status," not "404s.\" """

    def __init__(self, provider: CalendarProviderPort, access_token: str, calendar_id: str) -> None:
        self._provider = provider
        self._access_token = access_token
        self._calendar_id = calendar_id

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        event_id = execution_result.get("id")
        if not event_id:
            return False
        try:
            reloaded = await self._provider.get_event(
                self._access_token, calendar_id=self._calendar_id, event_id=event_id
            )
        except EchoError:
            return False
        return bool(reloaded.get("status") == "cancelled")
