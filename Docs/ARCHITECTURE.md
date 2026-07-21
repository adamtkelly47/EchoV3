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
        api/            # FastAPI app: routes, dependencies, middleware wiring
        worker/         # Worker entrypoint: job consumption loop
        scheduler/      # Scheduler entrypoint: schedule definitions, job creation
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
        conversation/
        approvals/      # populated Phase 6: models, schemas, errors, policies, service, repository
        capabilities/   # populated Phase 5: models, errors, policies, service (no repository.py —
                         # the registry is in-process/code-populated; only execution audit persists,
                         # via infrastructure/database's ToolCallRepository from Phase 4)
        portfolio/
        research/
        calendar/
        email/
        memory/
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
            schwab/
        calendar/
            google/
        email/
            gmail/
        research/
            sec/
            congressional/
            market_data/
            fundamentals/
            news/
    infrastructure/
        database/       # populated Phase 4: base.py, engine.py, tables/, repositories/
        queue/          # not yet populated — Redis is used directly by apps/ until a phase needs a repository-style abstraction over it
        cache/          # not yet populated
        secrets/        # not yet populated — no secret manager integration exists yet
        http/           # not yet populated
    api/
        routes/
        schemas/
        dependencies/
        middleware/
    tests/
        unit/
        integration/    # populated Phase 4: repository tests against the real Neon dev branch
        contract/
        end_to_end/
        fixtures/
        architecture/
    scripts/
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

## Application Layer (created as needed, not pre-scaffolded)

Per CONSTITUTION.md, `application/` will contain `capabilities/`, `orchestrators/`, `workflows/`, `commands/`, `queries/` once cross-domain coordination work begins (Phase 5+). It is not created empty during Phase 0 — creating unused orchestration folders now would violate the No Future Scaffolding Rule.

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
