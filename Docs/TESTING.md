Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Testing Strategy

## Purpose

This document defines Echo's testing pyramid, automated enforcement of coding standards, and CI gates, per PROMPT.md Sections 9 and 26 and CONSTITUTION.md's Testing Philosophy ("Testing is continuous. Not a final phase.").

## Testing Pyramid

Four layers, none relied on exclusively:

1. **Unit tests** (`tests/unit/`) — domain logic without network or database. Examples: approval state transitions, IPS rule evaluation, portfolio calculations, date logic, relevance-scoring rules, provenance record creation, model escalation policy.
2. **Integration tests** (`tests/integration/`) — PostgreSQL repositories, Redis queue behavior, OAuth token storage, provider adapters against recorded fixtures, Alembic migrations, Ollama structured-output behavior.
3. **Contract tests** (`tests/contract/`) — normalized provider interfaces against actual or sandboxed provider responses where permitted. A provider adapter must fail visibly, not silently degrade, when an external schema changes.
4. **End-to-end tests** (`tests/end_to_end/`) — full workflows using fake external adapters (e.g. ask for today's calendar, retrieve Schwab positions, create/approve/execute a calendar proposal against a test calendar, draft an email proposal, verify no action occurs before approval, modify a proposal and confirm prior approval is invalidated). Real external systems are exercised only through separate, explicitly controlled live verification scripts, never inside the automated suite.

## Coding Standards Enforcement

File and function size limits (ARCHITECTURE.md) are mechanically enforced, not just documented:

| Check | Threshold | Result |
|---|---|---|
| Function length | >500 lines | build failure |
| Function length | >300 lines | architecture review required |
| File length | >10,000 lines | soft ceiling, exceptional justification required |
| File length | >3,000 lines | architecture review required |
| Cyclomatic complexity | tool-defined threshold | review flag |
| Import cycles | any | build failure |
| Forbidden cross-domain / cross-layer imports | any (ARCHITECTURE.md dependency rules) | build failure |
| Dead code | tool-defined | review flag |
| Duplicate code | tool-defined | review flag |
| Type errors | any | build failure |
| Test coverage | below project threshold, set once a real baseline exists | review flag |
| Formatting violations | any | build failure |
| Security scan findings (high/critical) | any | build failure |

## Tooling (selected and verified in Phase 2)

Ruff (lint + format, including its `C90`/mccabe rule for complexity — used instead of a separate Radon dependency, one fewer tool to pin for the same metric family), MyPy in `strict` mode (chosen over Pyright — standard `pyproject.toml`-driven CI without adding a Node dependency to a Python job), Pytest + pytest-cov (testing/coverage), Vulture (dead code), Bandit (security), pip-audit (dependency vulnerability scanning), detect-secrets (secret scanning, run from the repo root — not scoped to `echo/` — since secrets can appear anywhere in the repo). Every one of these was actually run against the real codebase, not just configured; see `Docs/DECISION_LOG.md`'s Phase 2 entry for the real defects each one caught (mypy strict-mode errors, a bug in the architecture checker's own directory exclusion, and three real dependency CVEs pip-audit caught against pinned `pip`/`pytest`/`starlette`).

## Running Checks Locally

The host machine does not need a working Python/Node toolchain — everything runs inside the already-built `backend` image (Linux, matches CI's `ubuntu-latest` + Python 3.12) via a throwaway bind-mounted container:

```bash
docker run -d --name echo-devcheck --network echo_echo-internal --env-file .env \
  -v "<absolute-path-to-repo>/echo:/app" -w /app echo-backend sleep infinity
docker exec echo-devcheck pip install -e ".[dev]"

docker exec echo-devcheck ruff format --check .
docker exec echo-devcheck ruff check .
docker exec echo-devcheck mypy apps scripts core infrastructure migrations
docker exec echo-devcheck python scripts/check_size_limits.py apps core infrastructure
docker exec echo-devcheck python scripts/check_architecture.py .
docker exec echo-devcheck vulture apps core infrastructure scripts
docker exec echo-devcheck bandit -r apps core infrastructure -c pyproject.toml
docker exec echo-devcheck pip-audit
docker exec echo-devcheck pytest --cov --cov-report=term-missing

docker rm -f echo-devcheck   # when done
```

On Windows/Git Bash, prefix the `docker run` with `MSYS_NO_PATHCONV=1` — otherwise Git Bash rewrites the `-w /app` argument into a bogus Windows path. Do not use `docker cp` to sync repeated edits into a running container instead of a bind mount — `docker cp SRC_DIR CONTAINER:DEST_DIR` nests `SRC_DIR` inside an already-existing `DEST_DIR` rather than replacing its contents, which silently leaves stale files in place.

`tests/integration/` requires a real `DATABASE_URL` (the `--env-file .env` above provides it) and skips gracefully when one isn't set, so it's safe in CI even without a database configured there yet. Every integration test either never commits (rolled back on teardown) or explicitly deletes what it inserted — the real Neon dev branch used for local verification should show zero rows in any table after a full test run.

Frontend checks run directly with Node (already required for `npm run dev`):

```bash
cd frontend && npm install && npm run lint && npm run typecheck && npm run build
```

## Architecture Regression Tests

Architecture itself is tested (`tests/architecture/`), per CONSTITUTION.md's Architecture Regression Tests section. At minimum:

- API layer never imports providers directly.
- Domains never import other domains.
- Providers never expose vendor SDK types outside `providers/`.
- No domain imports a FastAPI route object or a raw DB session.
- No generic `shared/`/`common/`/`utils/` directory exists without an approved ADR.

A deliberately introduced forbidden import, an oversized function, a type error, or a failing test must each independently fail CI — this is itself a Phase 2 verification criterion (PROMPT.md Phase 2).

## Continuous Integration

CI runs, in order, on every change: formatting check, lint, type check, architecture tests, unit tests, integration tests, dependency vulnerability scan, secret scan. A failure at any stage blocks merge. Contract tests and end-to-end tests run as part of CI where they do not require live external credentials; live-provider verification scripts run separately and are never a merge gate (they depend on external system availability, which is explicitly assumed unreliable per the Constitution's External Systems section).

## Phase-Level Testing Discipline

Every implementation phase (CONTRIBUTING.md, PROMPT.md Section 28) adds tests as part of that phase's vertical slice, not as a follow-up. A phase is not complete until its verification commands actually pass — asserted, not assumed (Constitution: Phase Completion — "Verification shall be based on actual command results rather than assumption or assertion").
