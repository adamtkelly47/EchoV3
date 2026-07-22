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
from domains.research.service import (
    Form4ProviderPort,
    LegislatorReferencePort,
    NewsProviderPort,
    PtrProviderPort,
    ResearchProviderPort,
)
from providers.research.congress_legislators.adapter import CongressLegislatorsAdapter
from providers.research.finnhub.adapter import FinnhubAdapter
from providers.research.sec_edgar.adapter import SecEdgarAdapter
from providers.research.senate_efd.adapter import SenateEfdAdapter


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


def build_ptr_providers(settings: Settings) -> dict[str, PtrProviderPort]:
    """PROMPT.md Phase 19. The Senate eFD system is the only real PTR
    source this phase supports — the House Clerk's own disclosure system
    publishes PTRs as scanned PDFs, not structured data (a documented scope
    limitation, Docs/DECISION_LOG.md's Phase 19 entry) — but stays a dict
    for the same forward-compatible-without-scaffolding reason as
    `build_form4_providers`. Reuses `research_contact_email` for the same
    fair-access User-Agent purpose as `SecEdgarAdapter`, not a new
    credential."""
    providers: dict[str, PtrProviderPort] = {}
    if settings.research_contact_email:
        providers["senate_efd"] = SenateEfdAdapter(settings.research_contact_email)
    return providers


def build_legislator_reference_provider(settings: Settings) -> LegislatorReferencePort | None:
    """PROMPT.md Phase 19. Keyless and always available — no credential
    gate, unlike every other provider factory here — since
    `CongressLegislatorsAdapter` needs no API key or contact email at all.
    The `| None` return type matches `ResearchService.__init__`'s own
    `legislator_reference_provider: LegislatorReferencePort | None`
    parameter, which lets tests construct a service with no reference
    provider configured at all."""
    return CongressLegislatorsAdapter()
