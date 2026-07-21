"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in query params, matching apps/api/routes/conversations.py's and
apps/api/routes/memory.py's documented convention for this phase.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_calendar_service, get_db_session
from apps.api.schemas.calendar import (
    CalendarEventResponse,
    CalendarInfoResponse,
    CalendarListResponse,
    ConnectCallbackResponse,
    EventListResponse,
    FreeBusyPeriodResponse,
    FreeBusyResponse,
)
from domains.calendar.schemas import CalendarEvent
from domains.calendar.service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])


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
