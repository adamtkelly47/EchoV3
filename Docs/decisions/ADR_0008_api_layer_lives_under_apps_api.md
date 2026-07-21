Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0008: The API Layer Lives Under `apps/api/`, Not a Separate Top-Level `api/`

## Context

`ARCHITECTURE.md`'s repository tree (inherited from PROMPT.md's Section 7, carried through Phase 0 without being questioned) lists both `apps/api/` — commented "FastAPI app: routes, dependencies, middleware wiring" — and a separate top-level `api/` directory containing `routes/`, `schemas/`, `dependencies/`, `middleware/`. These duplicate the same subdirectory names with no stated relationship between them. This went unnoticed through Phases 1-7 because no phase needed real API routes beyond the Phase 1 health-check endpoints defined directly in `apps/api/main.py`. Phase 8 is the first phase that needs a real routes/schemas/dependencies structure, which is what surfaced the inconsistency.

## Decision

The API layer lives entirely under `apps/api/`: `apps/api/main.py` (app + middleware wiring, already established), `apps/api/routes/`, `apps/api/schemas/`, `apps/api/dependencies/`. The separate top-level `api/` directory from the original tree does not exist and is removed from `ARCHITECTURE.md`.

This matches ADR_0001's modular-monolith model directly: `apps/api` is one of the three runtime entrypoints (alongside `apps/worker`, `apps/scheduler`), and the API layer's routing/schema/dependency-injection code is part of that runtime, not a separate top-level concern with its own ambiguous relationship to the entrypoint that actually serves it.

## Alternatives Considered

**Keep both, with `apps/api/main.py` importing from the top-level `api/`.** Rejected — this recreates exactly the ownership ambiguity DOMAIN_OWNERSHIP.md's Single Owner Principle prohibits, just one layer up (repository-structure ambiguity instead of business-ownership ambiguity): two directories with the same names, no stated boundary between them, and no reason for a reader to know which one to extend.

**Move `apps/api/main.py` under the top-level `api/`.** Rejected — breaks the established `apps/{api,worker,scheduler}` symmetry from ADR_0001 for no benefit; `main.py` needs to stay where Docker's `CMD` and the existing Phase 1-7 code already expect it.

## Consequences

- `ARCHITECTURE.md`'s tree is corrected to remove the duplicate top-level `api/` entry.
- Phase 8's conversation routes are added at `apps/api/routes/conversations.py`, `apps/api/schemas/conversations.py`, `apps/api/dependencies.py`.
- Future phases adding API surface follow the same location — no ambiguity going forward.

## Reversal Conditions

None anticipated. If `apps/api` ever needed to be split into independently deployable services (a bigger change than this ADR covers), that would be its own ADR under ADR_0001's reversal conditions, not a reason to reintroduce a parallel `api/` directory.
