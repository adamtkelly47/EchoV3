"""Coordinates Calendar + Approvals for one write request — exactly what the
Application layer exists for (CONSTITUTION.md: "the only layer permitted to
coordinate more than one domain simultaneously"). Calendar writes always go
through the Approval Engine (Docs/APPROVAL_MODEL.md names Calendar as one of
its first two intended users) — this module is the only place a calendar
write proposal is created or executed; no domain-internal shortcut exists.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from core.errors import ValidationError
from domains.approvals.models import ProposalStatus, RiskLevel
from domains.approvals.schemas import ActionProposal
from domains.approvals.service import ApprovalService, WriteAdapter
from domains.calendar.models import RecurringEditScope
from domains.calendar.service import CalendarProviderPort, CalendarService
from domains.calendar.write_adapters import (
    CalendarCreateEventWriteAdapter,
    CalendarDeleteEventWriteAdapter,
    CalendarDeleteVerifier,
    CalendarModifyEventWriteAdapter,
    CalendarWriteVerifier,
)

_PROPOSAL_TTL = timedelta(hours=24)
_SCHEMA_VERSION = 1


def _google_datetime(when: datetime, *, all_day: bool, timezone: str | None) -> dict[str, Any]:
    if all_day:
        return {"date": when.date().isoformat()}
    node: dict[str, Any] = {"dateTime": when.isoformat()}
    if timezone:
        node["timeZone"] = timezone
    return node


class _CapturingWriteAdapter:
    """ApprovalService.execute() doesn't return the write adapter's raw
    result to its caller (Phase 6's own design — it returns the updated
    ActionProposal only) — wrapping the real adapter to capture the result
    lets the cache-sync step below see it without changing Phase 6 code."""

    def __init__(self, inner: WriteAdapter) -> None:
        self._inner = inner
        self.last_result: dict[str, Any] | None = None

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self._inner.execute(payload)
        self.last_result = result
        return result


class CalendarWriteOrchestrator:
    def __init__(
        self, approvals: ApprovalService, calendar: CalendarService, provider: CalendarProviderPort
    ) -> None:
        self._approvals = approvals
        self._calendar = calendar
        self._provider = provider

    async def propose_create_event(
        self,
        user_id: str,
        *,
        calendar_id: str = "primary",
        summary: str,
        start: datetime,
        end: datetime,
        all_day: bool = False,
        timezone: str | None = None,
        description: str | None = None,
    ) -> ActionProposal:
        payload: dict[str, Any] = {
            "action": "create_event",
            "calendar_id": calendar_id,
            "summary": summary,
            "start": _google_datetime(start, all_day=all_day, timezone=timezone),
            "end": _google_datetime(end, all_day=all_day, timezone=timezone),
        }
        if description is not None:
            payload["description"] = description
        return await self._propose(
            user_id,
            action_type="calendar.create_event",
            risk_level=RiskLevel.LOW,
            summary=f"Create calendar event: {summary}",
            payload=payload,
        )

    async def propose_modify_event(
        self,
        user_id: str,
        *,
        calendar_id: str = "primary",
        provider_event_id: str,
        recurring_event_id: str | None,
        scope: RecurringEditScope,
        summary: str | None = None,
        description: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        all_day: bool = False,
        timezone: str | None = None,
    ) -> ActionProposal:
        self._require_valid_scope(scope, recurring_event_id)
        payload: dict[str, Any] = {
            "action": "modify_event",
            "calendar_id": calendar_id,
            "provider_event_id": provider_event_id,
            "recurring_event_id": recurring_event_id,
            "scope": scope.value,
        }
        if summary is not None:
            payload["summary"] = summary
        if description is not None:
            payload["description"] = description
        if start is not None:
            payload["start"] = _google_datetime(start, all_day=all_day, timezone=timezone)
        if end is not None:
            payload["end"] = _google_datetime(end, all_day=all_day, timezone=timezone)
        return await self._propose(
            user_id,
            action_type="calendar.modify_event",
            risk_level=RiskLevel.LOW,
            summary=f"Modify calendar event {provider_event_id} ({scope.value})",
            payload=payload,
        )

    async def propose_delete_event(
        self,
        user_id: str,
        *,
        calendar_id: str = "primary",
        provider_event_id: str,
        recurring_event_id: str | None,
        scope: RecurringEditScope,
    ) -> ActionProposal:
        self._require_valid_scope(scope, recurring_event_id)
        payload = {
            "action": "delete_event",
            "calendar_id": calendar_id,
            "provider_event_id": provider_event_id,
            "recurring_event_id": recurring_event_id,
            "scope": scope.value,
        }
        return await self._propose(
            user_id,
            action_type="calendar.delete_event",
            # Deletion is comparatively harder to casually undo than create/
            # modify, even though Google Calendar keeps cancelled events
            # around for a time — a deliberate, documented risk distinction.
            risk_level=RiskLevel.MEDIUM,
            summary=f"Delete calendar event {provider_event_id} ({scope.value})",
            payload=payload,
        )

    async def execute_proposal(self, proposal_id: str, user_id: str) -> ActionProposal:
        proposal = await self._approvals.get_proposal(proposal_id)
        access_token = await self._calendar.get_valid_access_token(user_id)
        calendar_id = proposal.payload["calendar_id"]

        write_adapter, verifier = self._build_adapter_and_verifier(
            proposal.action_type, access_token, calendar_id
        )
        capturing = _CapturingWriteAdapter(write_adapter)
        executed = await self._approvals.execute(proposal_id, capturing, verifier)

        if executed.status == ProposalStatus.EXECUTED and capturing.last_result is not None:
            await self._sync_cache(
                user_id, executed.action_type, calendar_id, capturing.last_result
            )
        return executed

    async def _sync_cache(
        self, user_id: str, action_type: str, calendar_id: str, raw_result: dict[str, Any]
    ) -> None:
        if action_type == "calendar.delete_event":
            event_id = raw_result.get("id")
            if event_id:
                await self._calendar.evict_cached_event(user_id, event_id)
        else:
            await self._calendar.cache_event(user_id, calendar_id, raw_result)

    def _build_adapter_and_verifier(
        self, action_type: str, access_token: str, calendar_id: str
    ) -> tuple[Any, Any]:
        if action_type == "calendar.create_event":
            return (
                CalendarCreateEventWriteAdapter(self._provider, access_token),
                CalendarWriteVerifier(self._provider, access_token, calendar_id),
            )
        if action_type == "calendar.modify_event":
            return (
                CalendarModifyEventWriteAdapter(self._provider, access_token),
                CalendarWriteVerifier(self._provider, access_token, calendar_id),
            )
        if action_type == "calendar.delete_event":
            return (
                CalendarDeleteEventWriteAdapter(self._provider, access_token),
                CalendarDeleteVerifier(self._provider, access_token, calendar_id),
            )
        raise ValidationError(f"unknown calendar action_type: {action_type!r}")

    def _require_valid_scope(
        self, scope: RecurringEditScope, recurring_event_id: str | None
    ) -> None:
        if scope is RecurringEditScope.ENTIRE_SERIES and not recurring_event_id:
            raise ValidationError(
                "scope=entire_series requires recurring_event_id — "
                "the target event is not part of a recurring series"
            )

    async def _propose(
        self,
        user_id: str,
        *,
        action_type: str,
        risk_level: RiskLevel,
        summary: str,
        payload: dict[str, Any],
    ) -> ActionProposal:
        proposal = await self._approvals.propose(
            user_id=user_id,
            action_type=action_type,
            action_schema_version=_SCHEMA_VERSION,
            summary=summary,
            payload=payload,
            target_system="google_calendar",
            expected_effect=summary,
            risk_level=risk_level,
            required_permission="calendar.write",
            ttl=_PROPOSAL_TTL,
        )
        return await self._approvals.submit_for_approval(proposal.proposal_id)
