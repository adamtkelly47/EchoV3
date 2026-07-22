Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Architecture Map

## Purpose

This document is the concrete architecture map for Echo: the finalized repository structure, dependency rules, and container topology. CONSTITUTION.md establishes the layering and dependency principles as law; this document applies them to an actual tree. Where PROMPT.md Section 7 conflicts with this tree, this tree is authoritative — see ADR_0005.

## Container Topology

Per PROMPT.md Section 4/5 and ADR_0001 (Modular Monolith):

```text
Frontend (Next.js/TypeScript)      -- talks only to Backend API
Backend API (FastAPI/Python)       -- request/response, orchestration entrypoint
Worker (same codebase, own entrypoint) -- async/long-running jobs
Scheduler (same codebase, own entrypoint) -- creates jobs on a cadence, executes nothing itself
Neon Postgres                      -- sole system of record (ADR_0002)
Redis                              -- ephemeral/coordination only
Ollama                             -- local inference
Claude API                         -- hosted reasoning, via model gateway
```

Backend, Worker, and Scheduler are three separate runtime processes sharing one codebase and one set of domain modules. See ADR_0001.

## Repository Structure

At the repository root, `echo/` (Python backend/worker/scheduler) and `frontend/` (Next.js) sit alongside each other as separate build contexts, per the Container Philosophy ("Containers exist because of runtime requirements. Modules exist because of business ownership."):

```text
EchoV3/
    Docs/
    echo/          -- Python: apps/api, apps/worker, apps/scheduler share one codebase (ADR_0001)
    frontend/      -- Next.js/TypeScript, no business logic
    docker-compose.yml
    .env.example   -- placeholder only; real values live in gitignored .env (SECURITY.md)
```

Inside `echo/`:

```text
echo/
    apps/
        api/            # FastAPI app: main.py (entrypoint+middleware), routes/, schemas/,
                        # dependencies.py — the API layer lives entirely here (ADR_0008);
                        # there is no separate top-level api/ directory
        worker/         # Worker entrypoint: job consumption loop
        scheduler/      # Scheduler entrypoint: schedule definitions, job creation
    application/        # populated Phase 8 (ADR: none needed — just filling in the structure
                        # CONSTITUTION.md already specified once cross-domain coordination
                        # was first needed)
        capabilities/   # exposes platform capabilities not owned by a single domain (e.g.
                        # current_time)
        orchestrators/  # coordinates multiple domains for one complete request
    core/
        config/         # centralized configuration
        errors/         # common error taxonomy
        logging/        # structured logging
        security/       # permission classification (Phase 3); secret access lands with a later phase
        time/           # clock abstraction
        identifiers/    # id generation
        provenance/     # source record + computed value contracts
        events/         # generic event envelope contract — defined since an early phase but
                        # with no real publisher until Phase 26's ResponseChunkEvent/
                        # TranscriptChunkEvent (domains/conversation/events.py)
        jobs/           # generic job envelope contract — added in Phase 3, not the original
                        # Section 7 tree; kept distinct from events/ since a job is work still
                        # to be done, not a completed business fact (see ADR reasoning in
                        # Docs/DECISION_LOG.md's Phase 3 entry)
        observability/  # correlation context, metrics, tracing
        capabilities/   # the generic capability *contract* shape (Phase 3) — not the registry,
                        # which the Capabilities domain owns starting Phase 5
    domains/
        conversation/   # populated Phase 8: schemas, repository, service, errors. Phase 26 added
                        # events.py (TranscriptChunkPayload/ResponseChunkPayload, riding
                        # core/events/envelope.py's EventEnvelope) and interfaces.py
                        # (InterruptSignal) — voice preparation, no new provider
        approvals/      # populated Phase 6: models, schemas, errors, policies, service, repository.
                        # Phase 26 added ConfirmationMethod (models.py) and build_spoken_summary
                        # (policies.py) — the voice-safe approval requirement
        capabilities/   # populated Phase 5: models, errors, policies, service (no repository.py —
                         # the registry is in-process/code-populated; only execution audit persists,
                         # via infrastructure/database's ToolCallRepository from Phase 4)
        portfolio/      # populated Phase 12: models, schemas, errors, policies, service,
                         # repository — Schwab accounts/positions/balances/snapshots, reconciled
                         # against Schwab's own reported totals before being trusted. Phase 27
                         # extended it with HypotheticalTrade/HypotheticalPerformanceSample — no
                         # new domain (nothing here has an independent lifecycle Portfolio
                         # doesn't already own the natural extension of); no order/execute path
                         # anywhere, enforced by omission like Phase 12's own real-trading
                         # guarantee
        research/       # populated Phase 16: errors, policies, repository, schemas, service —
                         # provider-independent issuer identity/security master (models.py
                         # skipped; the one enum so far, EventType, lives in schemas.py
                         # alongside the record it classifies, matching Portfolio's AssetType
                         # precedent of colocating a schema's own vocabulary with it rather
                         # than a separate file for a single enum). Phase 17 added the news
                         # pipeline (NewsArticle/NewsDigest/NewsFeedback) as an extension of
                         # this same domain, not a new one — Docs/DOMAIN_OWNERSHIP.md already
                         # lists "News" under Research's own "Owns"
        calendar/       # populated Phase 10 (read): models, schemas, errors, policies, service,
                         # repository. Phase 11 (write) added write_adapters.py — concrete
                         # WriteAdapter/ExecutionVerifier implementations for the Approval Engine
        email/          # populated Phase 20 (read) + Phase 21 (write) in one pass: models,
                         # schemas, errors, policies, service, repository, write_adapters.py —
                         # an exact mirror of domains/calendar/'s Phase 10-11 split, since Gmail's
                         # OAuth/cache/approval-gated-write shape is structurally identical
        memory/         # populated Phase 9: models, schemas, errors, policies, service, repository
        knowledge/
        notifications/
        projects/       # populated Phase 23: models, schemas, errors, policies, service,
                         # repository. No provider port at all — Docs/DOMAIN_OWNERSHIP.md:
                         # "External Providers: None" — the first domain in this codebase
                         # built with zero external integration
        identity/
        system/         # populated Phase 24: models, schemas, errors, policies, repository,
                         # service. No provider port — like Projects, System coordinates other
                         # domains' already-synced state rather than talking to an external
                         # system directly; that coordination lives in
                         # application/orchestrators/monitoring.py. Phase 25 extended it with
                         # HallucinationIncident/RegressionCase — a human-reported concept and
                         # the "corrected failures" regression dataset PROMPT.md Phase 25 asks
                         # for, still no provider port
    providers/
        models/         # populated Phase 7: contracts.py, gateway.py, escalation.py
            claude/      # adapter.py, pricing.py — unit-tested against a mocked SDK client
                         # (no live API key in this dev environment)
            ollama/      # adapter.py — live-tested against the running container
        brokerage/
            schwab/      # populated Phase 12: adapter.py — plain httpx against Schwab's REST
                         # API (OAuth2 + trader/marketdata v1), verified live against a real
                         # connected account. HTTP Basic auth for token exchange (Schwab-specific
                         # — not body params like Google's)
        calendar/
            google/      # populated Phase 10: adapter.py — plain httpx against Google's REST
                         # APIs (OAuth2 + Calendar API v3), verified live against a real account
        email/
            gmail/      # populated Phase 20-21: adapter.py — plain httpx against Gmail's REST
                         # API (OAuth2 + Gmail API v1), endpoint/scope shapes verified against
                         # Google's own current documentation; not yet exercised against a real
                         # authenticated Gmail account (Docs/DECISION_LOG.md's Phase 20-21 entry)
        research/       # vendor-named subdirectories (finnhub/, sec_edgar/), matching every
                         # other populated providers/ subtree (calendar/google/, email/gmail/,
                         # brokerage/schwab/) — the original Phase 0 sketch here named these
                         # by research need instead (sec/, congressional/, market_data/,
                         # fundamentals/, news/), but a single vendor commonly serves more than
                         # one need (Finnhub alone covers fundamentals, earnings, analyst
                         # ratings, and company news), which the need-first sketch would have
                         # split the same adapter across; resolved the same way ADR_0005
                         # resolved other PROMPT.md Section 7 conflicts — this tree wins
            finnhub/    # populated Phase 16: adapter.py — live-verified in Phase 15
            sec_edgar/  # populated Phase 16: adapter.py — live-verified in Phase 15
    infrastructure/
        database/       # populated Phase 4: base.py, engine.py, tables/, repositories/
        queue/          # not yet populated — Redis is used directly by apps/ until a phase needs a repository-style abstraction over it
        cache/          # not yet populated
        secrets/        # populated Phase 10: encryption.py — Fernet-based encryption at rest
                         # for OAuth tokens (Docs/SECURITY.md), platform infra rather than a
                         # provider port since it isn't a swappable vendor integration
        http/           # not yet populated
    tests/
        unit/
        integration/    # populated Phase 4: repository tests against the real Neon dev branch
        contract/
        end_to_end/
        fixtures/
        architecture/
    scripts/            # check_architecture.py, check_size_limits.py; Phase 15 added
                         # provider_evaluation/ — a live-testing harness for candidate
                         # research-data providers, deliberately not domains/ or providers/
                         # (PROMPT.md Phase 15: "Do not select a permanent provider before
                         # this phase") — nothing in apps/domains/application imports it
    migrations/         # populated Phase 4: Alembic env.py + versions/
```

`echo/alembic.ini` sits at the `echo/` root (sibling to `pyproject.toml`), not nested under `migrations/` — Alembic's own convention.

(`Docs/` lives once, at the repository root, per the outer tree above — it is not duplicated inside `echo/`.)

Each `domains/<name>/` module follows the standard internal structure from CONSTITUTION.md when the responsibility is real and distinct: `models.py`, `schemas.py`, `repository.py`, `service.py`, `policies.py`, `events.py`, `errors.py`, `interfaces.py`. Additional files are added only when a responsibility genuinely requires them — not to imitate the pattern (No Future Scaffolding Rule).

This tree differs from PROMPT.md Section 7 as resolved by ADR_0005:

- `domains/integrations/` does not exist. Vendor logic lives under `providers/`.
- `domains/actions/` does not exist. Consequential execution lives inside `domains/approvals/` (Execution Ownership).
- `domains/documents/` does not exist. General reference material lives under `domains/knowledge/`; research-specific documents remain under `domains/research/`.
- `domains/capabilities/`, `domains/knowledge/` are present but not yet populated, matching DOMAIN_OWNERSHIP.md's catalog; `domains/system/` was populated in Phase 24.

## Dependency Rules

Dependency direction is one-way and absolute, per CONSTITUTION.md:

```text
Frontend -> API -> Application -> Domains -> Domain Interfaces -> Providers/Infrastructure -> External Systems
```

Concrete rules enforced by architecture tests (Phase 2):

| Rule | Enforcement |
|---|---|
| Domain modules must not import FastAPI route objects | forbidden-import test |
| Domain modules must not import vendor SDK response classes | forbidden-import test |
| Domain modules must not import a SQLAlchemy/DB session directly (only their own `repository.py`) | forbidden-import test |
| `domains/portfolio` must not import `domains/email`, `domains/calendar`, or any other domain | domain-isolation test |
| No domain-to-domain imports of any kind | domain-isolation test |
| `providers/*` implement `domains/*/interfaces.py`; never the reverse | dependency-direction test |
| `application/` is the only layer permitted to import more than one domain in the same function/module | orchestration-boundary test |
| No generic `shared/`, `common/`, `utils/`, `helpers/`, `misc/` directory without an approved ADR | structure test |

Cross-domain collaboration occurs only through the Application layer (`application/capabilities/`, `application/orchestrators/`, `application/workflows/`, `application/commands/`, `application/queries/` — created when Application-layer work begins) or through published domain events (DOMAIN_EVENTS.md). Direct domain-to-domain imports are a build failure, not a style warning.

## Application Layer

Per CONSTITUTION.md, `application/` contains `capabilities/`, `orchestrators/`, `workflows/`, `commands/`, `queries/` — populated one subdirectory at a time, only when something actually needs it (No Future Scaffolding). Phase 8 populated `capabilities/` (platform capabilities not owned by any single domain, e.g. `current_time`) and `orchestrators/` (`ConversationOrchestrator`, coordinating Conversation + Capabilities + the Model Gateway for one request). Phase 9 added a second orchestrator, `MemoryExtractionOrchestrator` (coordinating Memory + the Model Gateway to turn free text into candidate facts). Phase 10 added two more capabilities, `calendar.list_events`/`calendar.free_busy` (`application/capabilities/calendar_read.py`, wrapping `domains/calendar/`), plus `application/calendar_provider_factory.py` — a second instance of Phase 8's `model_gateway_factory.py` pattern (apps/ cannot import providers/ directly, so the Application layer constructs the concrete provider adapter and hands `apps/api/dependencies.py` a Protocol type instead). Phase 11 added a third orchestrator, `CalendarWriteOrchestrator` (coordinating Calendar + Approvals — proposing, and later executing, a calendar write through the Phase 6 Approval Engine). Phase 12 added `application/portfolio_provider_factory.py`, a third instance of the same provider-factory pattern (`build_schwab_provider`), constructing the concrete Schwab adapter and handing `apps/api/dependencies.py` a `PortfolioProviderPort` Protocol type instead. Phase 16 added `application/research_provider_factory.py` (`build_research_providers`) — a variant of the same pattern returning a `dict[str, ResearchProviderPort]` rather than a single adapter, since Research registers multiple providers (Finnhub, SEC EDGAR) simultaneously; a provider with no configured credential is simply omitted from the dict rather than registered with an adapter that would fail on first use. Phase 17 added a fourth orchestrator, `NewsIntelligenceOrchestrator` (`application/orchestrators/news_intelligence.py`) — the first orchestrator needing both the Model Gateway *and* a second domain (Portfolio, for a real portfolio-holding relevance boost) in the same pipeline; also added `build_news_providers` to `research_provider_factory.py`, a second, narrower provider dict for the one need (company news) not every research provider supports. Phase 18 added a fifth orchestrator, `InsiderIntelligenceOrchestrator` (`application/orchestrators/insider_intelligence.py`) — coordinating `domains/research/`'s deterministic Form 4 parsing/anomaly policies with the Model Gateway for footnote-context classification (Ollama) and an explicitly opt-in interpretation step (Claude, called only from its own `interpret()` method, never as a side effect of ingestion); also added `build_form4_providers` to `research_provider_factory.py`, a third, narrower provider dict for the one need (Form 4 filings) only SEC EDGAR supports. Phase 19 added no new orchestrator — every one of its implement items is a deterministic computation or a lookup against already-integrated data (no Model Gateway, no second domain), so the pipeline lives directly in `domains/research/service.py`. It added `build_ptr_providers` (a fourth, narrower provider dict — Senate PTR filings, Senate eFD only) and `build_legislator_reference_provider` (a single, always-available, keyless provider — the first provider-factory function in this codebase with no credential gate at all, since the congress-legislators reference dataset needs neither an API key nor a contact email) to `research_provider_factory.py`. Phase 22 populated `queries/` for the first time — `application/queries/dashboard_query.py`'s `DashboardQueryService` is a read-only cross-domain aggregation (Portfolio + Calendar + Approvals + Conversation) backing the unified dashboard, distinct from an orchestrator in that it coordinates domains for one read rather than one write workflow, but the same CONSTITUTION.md rule applies either way: only the Application layer may coordinate more than one domain at once. Phase 23 added a sixth orchestrator, `ProjectMemoryOrchestrator` (`application/orchestrators/project_memory.py`) — coordinating the new Projects domain with Memory so a recorded project decision also creates a linked, still-unconfirmed memory candidate; and extended `DashboardQueryService` to a fifth coordinated domain (Projects), replacing the dashboard's previously-placeholder Projects card with real data. Phase 24 added a seventh orchestrator, `MonitoringOrchestrator` (`application/orchestrators/monitoring.py`) — the first orchestrator coordinating four domains at once (System + Portfolio + Calendar + Research) for a single background sweep, and the first with no Model Gateway dependency at all (every monitor condition is a deterministic read of another domain's already-synced state). It also replaced the Phase 1 throwaway `echo:jobs:test` string-payload job with the first real `JobEnvelope[MonitoringEvaluateInput]` consumer/producer pair (`apps/scheduler/main.py`/`apps/worker/main.py`), on a dedicated `echo:jobs:monitoring` Redis queue. Phase 24's calendar-conflict check is the first concrete exercise of the domain-isolation rule (row above) from the System domain's side: `domains/system/policies.py`'s `find_calendar_conflicts` takes `list[tuple[str, datetime, datetime]]`, not `domains.calendar.schemas.CalendarEvent`, so `MonitoringOrchestrator` — not `domains/system/` — is the one place that ever imports both domains' schemas, translating typed Calendar events into plain primitives before handing them to System's policy function. Phase 25 added an eighth orchestrator, `TrustOrchestrator` (`application/orchestrators/trust.py`) — coordinating Memory + System so a user-initiated memory correction (`source_type="user_correction"`) also seeds a `RegressionCase` in System's own regression dataset, the one, unambiguous entry point that tells a real correction apart from any other, routine `MemoryService.supersede()` call. It also populated `queries/` a second time — `application/queries/trust_dashboard_query.py`'s `TrustDashboardQueryService` aggregates System, Portfolio, and the observability/audit repositories directly (matching `MonitoringOrchestrator`'s own precedent of an Application-layer component holding an `AuditRepository` reference directly, since audit/observability data is cross-cutting platform telemetry rather than any one domain's owned business state) into `GET /trust/dashboard`. Phases 20-21 added a ninth and tenth orchestrator: `EmailWriteOrchestrator` (`application/orchestrators/email_writes.py`) — a structural twin of `CalendarWriteOrchestrator`, coordinating Email + Approvals for all seven Gmail write actions — and `EmailIntelligenceOrchestrator` (`application/orchestrators/email_intelligence.py`) — coordinating Email + the Model Gateway for classification/action-items/response-needed (one combined Ollama call per message, not three) and on-demand thread summarization, matching `NewsIntelligenceOrchestrator`'s placement rationale. Also added `application/gmail_provider_factory.py` (`build_gmail_provider`), a fourth instance of the provider-factory pattern, and one new capability, `email.search_messages` (`application/capabilities/email_read.py`). `workflows/`, `commands/` remain unpopulated until a phase needs them.

## File and Function Discipline

Enforced numerically (see TESTING.md for tooling):

| | Preferred | Review | Strong review | Architecture review | Ceiling |
|---|---|---|---|---|---|
| Function lines | <50 | 100 | 150 | 300 | 500 (build failure) |
| File lines | <500 | 800 | 1,500 | 3,000 | 10,000 (soft) |

Directories should stay under ~15 files; 15 triggers review, 20 requires documented justification (split, submodule, or bounded context).

## Related Documents

- DOMAIN_OWNERSHIP.md — authoritative business ownership (this document does not redefine it)
- REQUEST_LIFECYCLE.md — how a request moves through these layers
- CAPABILITY_REGISTRY.md — capability contract detail
- APPROVAL_MODEL.md — approval state machine
- Docs/decisions/ADR_0001..0005 — decisions this map depends on
