"""API-boundary request/response schemas — never the domain's own
CalendarEvent/CalendarCredential crossing the wire directly (CONSTITUTION.md:
Typed Contracts), matching apps/api/schemas/conversations.py's convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConnectCallbackResponse(BaseModel):
    user_id: str
    connected: bool


class CalendarInfoResponse(BaseModel):
    calendar_id: str
    summary: str
    primary: bool
    time_zone: str | None


class CalendarListResponse(BaseModel):
    calendars: list[CalendarInfoResponse]


class CalendarEventResponse(BaseModel):
    event_id: str
    provider_event_id: str
    calendar_id: str
    summary: str
    description: str | None
    start: datetime
    end: datetime
    all_day: bool
    timezone: str | None
    status: str
    is_busy: bool
    recurring_event_id: str | None
    html_link: str | None
    synced_at: datetime


class EventListResponse(BaseModel):
    events: list[CalendarEventResponse]


class FreeBusyPeriodResponse(BaseModel):
    start: datetime
    end: datetime


class FreeBusyResponse(BaseModel):
    calendars: dict[str, list[FreeBusyPeriodResponse]]
