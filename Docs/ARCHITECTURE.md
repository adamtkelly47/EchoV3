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
        events/         # generic event envelope contract
        jobs/           # generic job envelope contract — added in Phase 3, not the original
                        # Section 7 tree; kept distinct from events/ since a job is work still
                        # to be done, not a completed business fact (see ADR reasoning in
                        # Docs/DECISION_LOG.md's Phase 3 entry)
        observability/  # correlation context, metrics, tracing
        capabilities/   # the generic capability *contract* shape (Phase 3) — not the registry,
                        # which the Capabilities domain owns starting Phase 5
    domains/
        conversation/   # populated Phase 8: schemas, repository, service, errors
        approvals/      # populated Phase 6: models, schemas, errors, policies, service, repository
        capabilities/   # populated Phase 5: models, errors, policies, service (no repository.py —
                         # the registry is in-process/code-populated; only execution audit persists,
                         # via infrastructure/database's ToolCallRepository from Phase 4)
        portfolio/      # populated Phase 12: models, schemas, errors, policies, service,
                         # repository — Schwab accounts/positions/balances/snapshots, reconciled
                         # against Schwab's own reported totals before being trusted
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
        email/
        memory/         # populated Phase 9: models, schemas, errors, policies, service, repository
        knowledge/
        notifications/
        projects/
        identity/
        system/
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
            gmail/
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
- `domains/capabilities/`, `domains/knowledge/`, `domains/system/` are present, matching DOMAIN_OWNERSHIP.md's catalog.

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

Per CONSTITUTION.md, `application/` contains `capabilities/`, `orchestrators/`, `workflows/`, `commands/`, `queries/` — populated one subdirectory at a time, only when something actually needs it (No Future Scaffolding). Phase 8 populated `capabilities/` (platform capabilities not owned by any single domain, e.g. `current_time`) and `orchestrators/` (`ConversationOrchestrator`, coordinating Conversation + Capabilities + the Model Gateway for one request). Phase 9 added a second orchestrator, `MemoryExtractionOrchestrator` (coordinating Memory + the Model Gateway to turn free text into candidate facts). Phase 10 added two more capabilities, `calendar.list_events`/`calendar.free_busy` (`application/capabilities/calendar_read.py`, wrapping `domains/calendar/`), plus `application/calendar_provider_factory.py` — a second instance of Phase 8's `model_gateway_factory.py` pattern (apps/ cannot import providers/ directly, so the Application layer constructs the concrete provider adapter and hands `apps/api/dependencies.py` a Protocol type instead). Phase 11 added a third orchestrator, `CalendarWriteOrchestrator` (coordinating Calendar + Approvals — proposing, and later executing, a calendar write through the Phase 6 Approval Engine). Phase 12 added `application/portfolio_provider_factory.py`, a third instance of the same provider-factory pattern (`build_schwab_provider`), constructing the concrete Schwab adapter and handing `apps/api/dependencies.py` a `PortfolioProviderPort` Protocol type instead. Phase 16 added `application/research_provider_factory.py` (`build_research_providers`) — a variant of the same pattern returning a `dict[str, ResearchProviderPort]` rather than a single adapter, since Research registers multiple providers (Finnhub, SEC EDGAR) simultaneously; a provider with no configured credential is simply omitted from the dict rather than registered with an adapter that would fail on first use. Phase 17 added a fourth orchestrator, `NewsIntelligenceOrchestrator` (`application/orchestrators/news_intelligence.py`) — the first orchestrator needing both the Model Gateway *and* a second domain (Portfolio, for a real portfolio-holding relevance boost) in the same pipeline; also added `build_news_providers` to `research_provider_factory.py`, a second, narrower provider dict for the one need (company news) not every research provider supports. Phase 18 added a fifth orchestrator, `InsiderIntelligenceOrchestrator` (`application/orchestrators/insider_intelligence.py`) — coordinating `domains/research/`'s deterministic Form 4 parsing/anomaly policies with the Model Gateway for footnote-context classification (Ollama) and an explicitly opt-in interpretation step (Claude, called only from its own `interpret()` method, never as a side effect of ingestion); also added `build_form4_providers` to `research_provider_factory.py`, a third, narrower provider dict for the one need (Form 4 filings) only SEC EDGAR supports. Phase 19 added no new orchestrator — every one of its implement items is a deterministic computation or a lookup against already-integrated data (no Model Gateway, no second domain), so the pipeline lives directly in `domains/research/service.py`. It added `build_ptr_providers` (a fourth, narrower provider dict — Senate PTR filings, Senate eFD only) and `build_legislator_reference_provider` (a single, always-available, keyless provider — the first provider-factory function in this codebase with no credential gate at all, since the congress-legislators reference dataset needs neither an API key nor a contact email) to `research_provider_factory.py`. Phase 22 populated `queries/` for the first time — `application/queries/dashboard_query.py`'s `DashboardQueryService` is a read-only cross-domain aggregation (Portfolio + Calendar + Approvals + Conversation) backing the unified dashboard, distinct from an orchestrator in that it coordinates domains for one read rather than one write workflow, but the same CONSTITUTION.md rule applies either way: only the Application layer may coordinate more than one domain at once. `workflows/`, `commands/` remain unpopulated until a phase needs them.

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
