"""Calendar read capabilities (PROMPT.md Phase 10 implement item 11:
"Calendar capability definitions"; Docs/CAPABILITY_REGISTRY.md: "Calendar
reads in Phase 10 ... register against this same contract — no phase
introduces a parallel or simplified registration mechanism"). Lives under
application/capabilities/ per CONSTITUTION.md's Application Structure, same
placement as application/capabilities/current_time.py — Calendar is a real
domain (unlike "current time"), but the *capability* wrapping still belongs
here since that's where every registered capability's thin adapter to a
domain service lives (the domain itself stays capability-agnostic).

Unlike current_time, these capabilities need database access. The
capability registry is built once at process start (apps/api/dependencies.py's
`get_capability_registry` is `@lru_cache`d), before any per-request session
exists — so each handler opens its own `session_scope()` per call rather
than closing over a single fixed session the way current_time closes over a
fixed Clock. This makes capability execution a self-contained transaction,
consistent with CONSTITUTION.md's Capability Execution pipeline treating
execution as one atomic step.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.capabilities import CapabilityContract, ExecutionEnvironment, ReadWriteClassification
from core.security import Permission, PermissionAction
from core.time import SystemClock
from domains.calendar.repository import (
    PostgresCalendarCredentialRepository,
    PostgresCalendarEventRepository,
)
from domains.calendar.service import CalendarProviderPort, CalendarService
from domains.capabilities.models import RegisteredCapability
from infrastructure.database.engine import session_scope
from infrastructure.database.repositories.audit import PostgresAuditRepository
from infrastructure.secrets.encryption import SecretCipher

LIST_EVENTS_CAPABILITY_ID = "calendar.list_events"
FREE_BUSY_CAPABILITY_ID = "calendar.free_busy"

_READ_PERMISSION = [Permission(resource="calendar", action=PermissionAction.READ)]


class ListEventsInput(BaseModel):
    user_id: str
    time_min: datetime
    time_max: datetime
    query: str | None = None


class CalendarEventSummary(BaseModel):
    provider_event_id: str
    summary: str
    start: datetime
    end: datetime
    all_day: bool
    is_busy: bool
    recurring_event_id: str | None


class ListEventsOutput(BaseModel):
    events: list[CalendarEventSummary]


class FreeBusyInput(BaseModel):
    user_id: str
    time_min: datetime
    time_max: datetime


class FreeBusyPeriodOutput(BaseModel):
    start: datetime
    end: datetime


class FreeBusyOutput(BaseModel):
    busy: list[FreeBusyPeriodOutput]


def _build_calendar_service(
    session: AsyncSession, provider: CalendarProviderPort, cipher: SecretCipher, state_secret: str
) -> CalendarService:
    return CalendarService(
        PostgresCalendarCredentialRepository(session),
        PostgresCalendarEventRepository(session),
        provider,
        cipher,
        PostgresAuditRepository(session),
        SystemClock(),
        state_secret,
    )


def build_calendar_list_events_capability(
    provider: CalendarProviderPort, cipher: SecretCipher, state_secret: str
) -> RegisteredCapability:
    async def handler(raw_data: BaseModel) -> BaseModel:
        # CapabilityExecutor._validate_input already guarantees raw_data is
        # exactly this handler's input_model — a type-narrowing cast, not a
        # runtime invariant check (an assert would be stripped under -O).
        data = cast(ListEventsInput, raw_data)
        async with session_scope() as session:
            calendar = _build_calendar_service(session, provider, cipher, state_secret)
            events = await calendar.list_events(
                data.user_id, time_min=data.time_min, time_max=data.time_max, query=data.query
            )
        return ListEventsOutput(
            events=[
                CalendarEventSummary(
                    provider_event_id=e.provider_event_id,
                    summary=e.summary,
                    start=e.start,
                    end=e.end,
                    all_day=e.all_day,
                    is_busy=e.is_busy,
                    recurring_event_id=e.recurring_event_id,
                )
                for e in events
            ]
        )

    contract = CapabilityContract(
        capability_id=LIST_EVENTS_CAPABILITY_ID,
        version=1,
        display_name="List calendar events",
        description=(
            "Lists (optionally searches) the user's primary Google Calendar events in a time range."
        ),
        owner="Calendar",
        input_schema=ListEventsInput.model_json_schema(),
        output_schema=ListEventsOutput.model_json_schema(),
        permission_requirements=_READ_PERMISSION,
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=30,
        idempotency_behavior="read only — safe to call repeatedly",
        provenance_requirements="source=google_calendar; synced_at recorded per event",
        supported_interfaces=["chat", "api"],
        expected_errors=["calendar_credential_not_found", "calendar_token_refresh_failed"],
    )
    return RegisteredCapability(
        contract=contract,
        input_model=ListEventsInput,
        output_model=ListEventsOutput,
        handler=handler,
    )


def build_calendar_free_busy_capability(
    provider: CalendarProviderPort, cipher: SecretCipher, state_secret: str
) -> RegisteredCapability:
    async def handler(raw_data: BaseModel) -> BaseModel:
        data = cast(FreeBusyInput, raw_data)
        async with session_scope() as session:
            calendar = _build_calendar_service(session, provider, cipher, state_secret)
            result = await calendar.free_busy(
                data.user_id,
                calendar_ids=["primary"],
                time_min=data.time_min,
                time_max=data.time_max,
            )
        return FreeBusyOutput(
            busy=[FreeBusyPeriodOutput(start=p.start, end=p.end) for p in result.get("primary", [])]
        )

    contract = CapabilityContract(
        capability_id=FREE_BUSY_CAPABILITY_ID,
        version=1,
        display_name="Calendar free/busy",
        description=(
            "Returns busy time periods on the user's primary Google Calendar in a time range."
        ),
        owner="Calendar",
        input_schema=FreeBusyInput.model_json_schema(),
        output_schema=FreeBusyOutput.model_json_schema(),
        permission_requirements=_READ_PERMISSION,
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=30,
        idempotency_behavior="read only — safe to call repeatedly",
        provenance_requirements="source=google_calendar",
        supported_interfaces=["chat", "api"],
        expected_errors=["calendar_credential_not_found", "calendar_token_refresh_failed"],
    )
    return RegisteredCapability(
        contract=contract, input_model=FreeBusyInput, output_model=FreeBusyOutput, handler=handler
    )
