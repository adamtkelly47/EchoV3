"""Constructs the concrete Gmail provider adapter from settings — same
purpose and shape as application/calendar_provider_factory.py: apps/ must
not import providers/ directly (scripts/check_architecture.py's
apps-must-not-import-providers rule), so the composition root needs an
application-layer factory to depend on instead.
"""

from __future__ import annotations

from core.config import Settings
from domains.email.service import EmailProviderPort
from providers.email.gmail.adapter import GmailAdapter


def build_gmail_provider(settings: Settings) -> EmailProviderPort:
    return GmailAdapter(
        client_id=settings.gmail_client_id or "",
        client_secret=settings.gmail_client_secret or "",
        redirect_uri=settings.gmail_redirect_uri,
    )
