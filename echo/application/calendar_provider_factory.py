"""Constructs the concrete Google Calendar provider adapter from settings —
same purpose and shape as application/model_gateway_factory.py: apps/ must
not import providers/ directly (scripts/check_architecture.py's
apps-must-not-import-providers rule), including for a bare return-type
annotation, so the composition root needs an application-layer factory to
depend on instead. Construction of concrete provider adapters happens at
the Application layer, which sits between API and Providers in the
dependency direction (CONSTITUTION.md: "No layer may bypass intermediate
ownership.").
"""

from __future__ import annotations

from core.config import Settings
from domains.calendar.service import CalendarProviderPort
from providers.calendar.google.adapter import GoogleCalendarAdapter


def build_google_calendar_provider(settings: Settings) -> CalendarProviderPort:
    return GoogleCalendarAdapter(
        client_id=settings.google_oauth_client_id or "",
        client_secret=settings.google_oauth_client_secret or "",
        redirect_uri=settings.google_oauth_redirect_uri,
    )
