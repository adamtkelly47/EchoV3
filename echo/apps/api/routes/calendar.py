"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in query params, matching apps/api/routes/conversations.py's and
apps/api/routes/memory.py's documented convention for this phase.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.calendar_writes import CalendarWriteOrchestrator
from apps.api.dependencies import (
    get_calendar_service,
    get_calendar_write_orchestrator,
    get_db_session,
)
from apps.api.schemas.approvals import ProposalResponse
from apps.api.schemas.calendar import (
    CalendarEventResponse,
    CalendarInfoResponse,
    CalendarListResponse,
    ConnectCallbackResponse,
    CreateEventRequest,
    EventListResponse,
    FreeBusyPeriodResponse,
    FreeBusyResponse,
    ModifyEventRequest,
)
from core.errors import ValidationError
from domains.approvals.schemas import ActionProposal
from domains.calendar.models import RecurringEditScope
from domains.calendar.schemas import CalendarEvent
from domains.calendar.service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _to_proposal_response(proposal: ActionProposal) -> ProposalResponse:
    return ProposalResponse(
        proposal_id=proposal.proposal_id,
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        summary=proposal.summary,
        payload=proposal.payload,
        target_system=proposal.target_system,
        expected_effect=proposal.expected_effect,
        risk_level=proposal.risk_level.value,
        status=proposal.status.value,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        warnings=proposal.warnings,
    )


def _parse_scope(scope: str) -> RecurringEditScope:
    try:
        return RecurringEditScope(scope)
    except ValueError as exc:
        raise ValidationError(
            f"scope must be one of {[s.value for s in RecurringEditScope]}, got {scope!r}"
        ) from exc


def _to_response(event: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        event_id=event.event_id,
        provider_event_id=event.provider_event_id,
        calendar_id=event.calendar_id,
        summary=event.summary,
        description=event.description,
        start=event.start,
        end=event.end,
        all_day=event.all_day,
        timezone=event.timezone,
        status=event.status.value,
        is_busy=event.is_busy,
        recurring_event_id=event.recurring_event_id,
        html_link=event.html_link,
        synced_at=event.synced_at,
    )


@router.get("/oauth/authorize")
async def authorize(
    user_id: str, calendar: CalendarService = Depends(get_calendar_service)
) -> RedirectResponse:
    return RedirectResponse(calendar.start_authorization(user_id))


@router.get("/oauth/callback", response_model=ConnectCallbackResponse)
async def callback(
    code: str,
    state: str,
    calendar: CalendarService = Depends(get_calendar_service),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectCallbackResponse:
    credential = await calendar.complete_authorization(code, state)
    await session.commit()
    return ConnectCallbackResponse(user_id=credential.user_id, connected=True)


@router.get("/calendars", response_model=CalendarListResponse)
async def list_calendars(
    user_id: str, calendar: CalendarService = Depends(get_calendar_service)
) -> CalendarListResponse:
    calendars = await calendar.list_calendars(user_id)
    return CalendarListResponse(
        calendars=[
            CalendarInfoResponse(
                calendar_id=c.calendar_id,
                summary=c.summary,
                primary=c.primary,
                time_zone=c.time_zone,
            )
            for c in calendars
        ]
    )


@router.get("/events", response_model=EventListResponse)
async def list_events(
    user_id: str,
    time_min: datetime,
    time_max: datetime,
    query: str | None = None,
    calendar_id: str = "primary",
    calendar: CalendarService = Depends(get_calendar_service),
    session: AsyncSession = Depends(get_db_session),
) -> EventListResponse:
    events = await calendar.list_events(
        user_id, calendar_id=calendar_id, time_min=time_min, time_max=time_max, query=query
    )
    await session.commit()
    return EventListResponse(events=[_to_response(e) for e in events])


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: str,
    user_id: str,
    calendar_id: str = "primary",
    calendar: CalendarService = Depends(get_calendar_service),
    session: AsyncSession = Depends(get_db_session),
) -> CalendarEventResponse:
    event = await calendar.get_event(user_id, calendar_id=calendar_id, event_id=event_id)
    await session.commit()
    return _to_response(event)


@router.get("/freebusy", response_model=FreeBusyResponse)
async def free_busy(
    user_id: str,
    time_min: datetime,
    time_max: datetime,
    calendar_id: str = "primary",
    calendar: CalendarService = Depends(get_calendar_service),
) -> FreeBusyResponse:
    result = await calendar.free_busy(
        user_id, calendar_ids=[calendar_id], time_min=time_min, time_max=time_max
    )
    return FreeBusyResponse(
        calendars={
            cal_id: [FreeBusyPeriodResponse(start=p.start, end=p.end) for p in periods]
            for cal_id, periods in result.items()
        }
    )


@router.post("/events", response_model=ProposalResponse)
async def propose_create_event(
    body: CreateEventRequest,
    orchestrator: CalendarWriteOrchestrator = Depends(get_calendar_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_create_event(
        body.user_id,
        calendar_id=body.calendar_id,
        summary=body.summary,
        start=body.start,
        end=body.end,
        all_day=body.all_day,
        timezone=body.timezone,
        description=body.description,
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.patch("/events/{provider_event_id}", response_model=ProposalResponse)
async def propose_modify_event(
    provider_event_id: str,
    body: ModifyEventRequest,
    orchestrator: CalendarWriteOrchestrator = Depends(get_calendar_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_modify_event(
        body.user_id,
        calendar_id=body.calendar_id,
        provider_event_id=provider_event_id,
        recurring_event_id=body.recurring_event_id,
        scope=_parse_scope(body.scope),
        summary=body.summary,
        description=body.description,
        start=body.start,
        end=body.end,
        all_day=body.all_day,
        timezone=body.timezone,
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.delete("/events/{provider_event_id}", response_model=ProposalResponse)
async def propose_delete_event(
    provider_event_id: str,
    user_id: str,
    calendar_id: str = "primary",
    recurring_event_id: str | None = None,
    scope: str = "single_instance",
    orchestrator: CalendarWriteOrchestrator = Depends(get_calendar_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_delete_event(
        user_id,
        calendar_id=calendar_id,
        provider_event_id=provider_event_id,
        recurring_event_id=recurring_event_id,
        scope=_parse_scope(scope),
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/proposals/{proposal_id}/execute", response_model=ProposalResponse)
async def execute_proposal(
    proposal_id: str,
    user_id: str,
    orchestrator: CalendarWriteOrchestrator = Depends(get_calendar_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.execute_proposal(proposal_id, user_id)
    await session.commit()
    return _to_proposal_response(proposal)
