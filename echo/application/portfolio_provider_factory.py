"""Constructs the concrete Schwab provider adapter from settings — same
purpose and shape as application/calendar_provider_factory.py and
application/model_gateway_factory.py: apps/ must not import providers/
directly (scripts/check_architecture.py's apps-must-not-import-providers
rule), so the composition root needs an application-layer factory to
depend on instead.
"""

from __future__ import annotations

from core.config import Settings
from domains.portfolio.service import PortfolioProviderPort
from providers.schwab.adapter import SchwabAdapter


def build_schwab_provider(settings: Settings) -> PortfolioProviderPort:
    return SchwabAdapter(
        client_id=settings.schwab_client_id or "",
        client_secret=settings.schwab_client_secret or "",
        redirect_uri=settings.schwab_redirect_uri,
    )
