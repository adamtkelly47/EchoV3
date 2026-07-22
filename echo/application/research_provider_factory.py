"""Constructs the dict of concrete research provider adapters from settings
— same purpose and shape as application/portfolio_provider_factory.py and
application/calendar_provider_factory.py: apps/ must not import providers/
directly (scripts/check_architecture.py's apps-must-not-import-providers
rule), so the composition root needs an application-layer factory to depend
on instead.

Unlike Calendar/Portfolio's single provider each, Research registers
multiple providers simultaneously under one dict, keyed by the same name
domains/research/service.py's `sync_issuer` dispatches on — PROMPT.md Phase
16's own point: the domain is provider-independent, so this is the only
place that knows which concrete adapters currently back "finnhub" and
"sec_edgar". A provider with no configured credential is simply omitted
rather than registered with an adapter that would fail on first use.
"""

from __future__ import annotations

from core.config import Settings
from domains.research.service import Form4ProviderPort, NewsProviderPort, ResearchProviderPort
from providers.research.finnhub.adapter import FinnhubAdapter
from providers.research.sec_edgar.adapter import SecEdgarAdapter


def build_research_providers(settings: Settings) -> dict[str, ResearchProviderPort]:
    providers: dict[str, ResearchProviderPort] = {}
    if settings.finnhub_api_key:
        providers["finnhub"] = FinnhubAdapter(settings.finnhub_api_key)
    if settings.research_contact_email:
        providers["sec_edgar"] = SecEdgarAdapter(settings.research_contact_email)
    return providers


def build_news_providers(settings: Settings) -> dict[str, NewsProviderPort]:
    """PROMPT.md Phase 17. A separate dict/factory from
    `build_research_providers` — SEC EDGAR has no news endpoint at all, so
    forcing one shared Protocol across both needs would either give
    `SecEdgarAdapter` a method it can never honestly implement, or force
    `ResearchProviderPort` itself to grow a method most providers don't
    support. `FinnhubAdapter` structurally satisfies both Protocols; a
    second instance here (rather than sharing the one from
    `build_research_providers`) is a stateless adapter holding only an API
    key, so the duplication costs nothing."""
    providers: dict[str, NewsProviderPort] = {}
    if settings.finnhub_api_key:
        providers["finnhub"] = FinnhubAdapter(settings.finnhub_api_key)
    return providers


def build_form4_providers(settings: Settings) -> dict[str, Form4ProviderPort]:
    """PROMPT.md Phase 18. SEC EDGAR is the only provider with Form 4 data
    — Finnhub has no filings endpoint — so this dict will only ever have
    one entry in practice, but stays a dict (not a single adapter) for the
    same reason `build_research_providers` does: nothing about the
    `Form4ProviderPort` shape assumes there's exactly one implementation
    forever (PROMPT.md Phase 16 verification 3: "provider replacement does
    not alter domain interfaces")."""
    providers: dict[str, Form4ProviderPort] = {}
    if settings.research_contact_email:
        providers["sec_edgar"] = SecEdgarAdapter(settings.research_contact_email)
    return providers
