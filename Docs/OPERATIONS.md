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

## Ollama Models

The `ollama` container starts with no models pulled — pulling a model is a multi-gigabyte download and is not required for Phase 1's reachability check. To pull a model for later phases (once model-gateway work begins in Phase 7):

```bash
docker compose exec ollama ollama pull <model-name>
```

Model selection itself is a Phase 7 decision (`MODEL_ROUTING.md`), not made here.

## Known Limitations (Phase 1)

- No formatting/linting/type-checking/CI is wired in yet — that is Phase 2's deliverable. Code in `echo/` and `frontend/` has been written carefully but not mechanically verified against the standards in `TESTING.md`.
- The worker/scheduler test job (`echo:jobs:test` on Redis) is throwaway plumbing to prove the queue works end to end. It is replaced by the real typed Job Envelope contract in Phase 3.
- `apps/api/main.py` reads configuration directly from environment variables. Centralized `core/config` lands in Phase 3.
