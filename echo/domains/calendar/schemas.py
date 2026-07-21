"""Calendar's own data contracts (Docs/DOMAIN_OWNERSHIP.md: Calendar owns
Calendar Events, Availability, Calendar Synchronization). No field list
exists in Docs/DATA_MODEL.md to mirror — derived from Google Calendar API
v3's real Event resource (developers.google.com/calendar/api/v3/reference/
events, verified live per CONSTITUTION.md's Provider Due Diligence) but
kept provider-agnostic in field naming, matching domains/calendar/models.py.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.calendar.models import EventStatus


class CalendarCredential(BaseModel):
    """OAuth token state for one user's connection to one provider. Tokens
    are stored encrypted (Docs/SECURITY.md) — this schema holds ciphertext,
    never plaintext tokens; domains/calendar/service.py is the only place
    that ever sees a decrypted token, and only for the duration of a single
    provider call."""

    credential_id: str = Field(default_factory=lambda: new_id("calcred"))
    user_id: str
    provider: str = "google"
    encrypted_access_token: str
    encrypted_refresh_token: str
    access_token_expires_at: datetime
    scope: str
    created_at: datetime
    updated_at: datetime


class CalendarEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("calevent"))
    user_id: str
    provider_event_id: str
    calendar_id: str
    summary: str
    description: str | None = None
    start: datetime
    end: datetime
    all_day: bool = False
    timezone: str | None = None
    status: EventStatus = EventStatus.CONFIRMED
    is_busy: bool = True
    # Set only for an instance of a recurring event, pointing at the parent
    # (Docs/PROMPT.md Phase 10 implement item 7: recurring event
    # normalization) — None for a non-recurring or parent event.
    recurring_event_id: str | None = None
    html_link: str | None = None
    # When this event was last fetched from the provider (PROMPT.md Phase
    # 10 implement items 9-10: calendar cache, freshness handling) — set by
    # domains/calendar/service.py using its injected Clock, never by a
    # provider adapter (core.time.Clock: "the platform owns time").
    synced_at: datetime


class FreeBusyPeriod(BaseModel):
    start: datetime
    end: datetime


class CalendarInfo(BaseModel):
    calendar_id: str
    summary: str
    primary: bool = False
    time_zone: str | None = None
