Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Operations

## Purpose

This document was intentionally deferred at Phase 0 (see `DECISION_LOG.md`, 2026-07-20) because no deployable containers existed to document. Phase 1 (Docker development foundation) now exists, so this covers local environment setup, startup, and secret handling. Deployment/production operations are added when a deployed environment exists — this document does not speculate about that yet.

## Prerequisites

- Docker Desktop (or equivalent Docker Engine + Compose v2).
- A Neon account and project (see `Docs/decisions/ADR_0002` and `ADR_0006`). Use a dedicated development branch, not a production branch.

## One-Command Startup

```bash
cp .env.example .env      # then fill in real values — see Secret Handling below
docker compose up --build
```

This builds and starts five services: `frontend` (localhost:3000), `backend` (localhost:8000), `worker`, `scheduler`, `redis`, and `ollama`. `redis` and `ollama` are not published to the host — they are reachable only from other containers on the `echo-internal` network, per `SECURITY.md`.

Restarting containers (`docker compose restart` or `down` + `up`) does not erase Neon data (Neon is external to the Compose stack) and does not erase Ollama's pulled models (stored in the `ollama_data` named volume).

`docker compose restart <service>` restarts the running process but does **not** re-read `env_file` (`.env`) — a variable added to `.env` after the container was created stays invisible until the container is recreated with `docker compose up -d <service>` (or `up --build` for a code change). Confirmed the hard way in Phase 15's Decision Log entry: `restart` alone left two newly-added API keys unset even though `.env` had them, and `up -d` was required to pick them up. Recreating also wipes anything installed or copied into the container outside the image build (dev tools from `pip install ".[dev]"`, any file placed via `docker compose cp`) — both need redoing after a recreate, not just a restart.

## Verifying the Environment

```bash
curl http://localhost:8000/health                # liveness — always 200 once the process is up
curl http://localhost:8000/health/dependencies    # readiness — checks Neon, Redis, Ollama reachability
curl http://localhost:3000/                       # frontend status page
docker compose logs worker                        # should show "received test job" every ~30s
```

`/health/dependencies` returning `"status": "degraded"` with `database.ok: false` most commonly means `.env`'s `DATABASE_URL` is missing, wrong, or the Neon branch is suspended (Neon auto-suspends idle compute — the first query after suspend has a brief cold-start delay, which is expected, not a failure).

## Secret Handling Conventions

- `.env.example` is committed and contains placeholders only. `.env` is gitignored (`.gitignore`) and is never committed.
- The real `DATABASE_URL` is obtained from the Neon console or the Neon CLI/MCP integration and pasted only into the local `.env` file — never into a committed file, never into documentation, never into a chat transcript.
- If a secret is ever accidentally committed, deleting it in a later commit is **not sufficient** — git history retains it. The credential must be rotated (regenerated in Neon's console) and the old one invalidated.
- Development and any future production credentials use separate Neon branches / separate secrets; they are never shared.

## Database Migrations

Schema changes go through Alembic (`echo/migrations/`), never hand-run SQL (`CONSTITUTION.md`: Migrations). Migrations run against the deployed `backend` container, which has the same code and `DATABASE_URL` as the running app:

```bash
docker compose exec backend alembic current           # what revision is applied
docker compose exec backend alembic upgrade head       # apply pending migrations
docker compose exec backend alembic downgrade -1        # revert the last migration
docker compose exec backend alembic revision --autogenerate -m "add portfolio tables"  # after adding/changing ORM models
```

Autogenerate compares `infrastructure/database/tables/` (via `infrastructure/database/base.Base.metadata`) against the live database — review the generated migration before applying it; autogenerate detects structural changes but not every intent (e.g. column renames show up as drop+add unless edited by hand).

Neon-specific note: `infrastructure/database/engine.py` strips `sslmode`/`channel_binding` from the connection string and translates them into asyncpg's own `ssl=` connect arg, and disables asyncpg's prepared-statement cache (`statement_cache_size=0`). Both are required for the pooled (`-pooler`) endpoint — asyncpg's `connect()` has no `sslmode` parameter, and Neon's pooler runs PgBouncer in transaction mode, which doesn't support asyncpg's server-side prepared-statement cache across pooled connections. If you ever bypass `create_engine()` and construct a connection another way, both issues resurface.

## Ollama Models

The `ollama` container starts with no models pulled — pulling a model is a multi-gigabyte download and is not required for Phase 1's reachability check. To pull a model for later phases (once model-gateway work begins in Phase 7):

```bash
docker compose exec ollama ollama pull <model-name>
```

Model selection itself is a Phase 7 decision (`MODEL_ROUTING.md`), not made here.

## Known Limitations (as of Phase 4)

- The worker/scheduler test job (`echo:jobs:test` on Redis) is still throwaway plumbing to prove the queue works end to end — it has not been upgraded to the real typed `core.jobs.JobEnvelope` contract. That happens once a real job type is introduced (Phase 24 or earlier).
- No domain owns the tables in `infrastructure/database/tables/` yet — they are cross-cutting platform tables (audit, jobs, provenance, model/tool call telemetry). Domain-specific tables (Portfolio positions, Calendar events, etc.) begin Phase 8+.
- Nothing in `apps/` reads from or writes to the database yet. The repository layer exists and is verified against real Postgres, but no request path calls it — that begins with the Capability Registry (Phase 5).
