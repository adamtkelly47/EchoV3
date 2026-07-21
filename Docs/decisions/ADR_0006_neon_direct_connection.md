Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0006: Local Development Connects Directly to Neon (No Local Postgres Container)

## Context

PROMPT.md's Phase 1 container list (Section 29) literally includes "PostgreSQL" as one of the Docker Compose services. ADR_0002 already established Neon serverless Postgres as the sole system of record for all environments, and PROMPT.md Section 5.5 states this is an explicit user requirement, not a default. The user has since created a Neon account specifically for this project.

Running a separately containerized local Postgres alongside Neon would reintroduce exactly the "two systems of record" risk ADR_0002 exists to prevent: schema drift between the local container and Neon, and behavioral differences between a stock Postgres driver and Neon's connection/pooling model (e.g. the `-pooler` endpoint suffix, serverless HTTP driver options) that would go untested locally and surface only in a deployed environment.

## Decision

Docker Compose does not run a local Postgres container. The backend, worker, and scheduler containers connect directly to a Neon Postgres branch via a `DATABASE_URL` environment variable, sourced from an untracked `.env` file (see `.env.example` and `SECURITY.md`) — never hardcoded, never committed.

For local development, a dedicated Neon branch is used, isolated from any future production branch, using Neon's instant copy-on-write branching. This means local development and testing can create/drop data freely without any risk to a production branch, and without a full data copy.

The backend's `/health/dependencies` endpoint verifies Neon reachability the same way it would in any deployed environment — there is no separate "local-only" database code path.

## Alternatives Considered

**Run a local containerized Postgres for offline development, use Neon only in deployed environments.** Rejected: reintroduces a second system of record and a second connection code path, in direct tension with ADR_0002's rationale ("Business ownership determines persistence ownership" / one authoritative store). It would also mean the Neon-specific connection behavior (pooling, branching, sslmode requirements) never gets exercised until a real deployment, which is precisely the kind of environment-integrity gap CONSTITUTION.md's Environment Integrity section warns against.

**Use Neon's local proxy tooling to emulate a local Postgres port while still talking to Neon.** Considered but not adopted for Phase 1 — it adds a component with no demonstrated need yet; DATABASE_URL pointed at a real Neon dev branch is simpler and satisfies every Phase 1 verification criterion. May be reconsidered if a concrete workflow requirement (e.g. fully offline development) emerges.

## Consequences

- Local development requires network access to Neon; there is currently no fully offline mode. This is an accepted tradeoff given the user's explicit Neon requirement.
- `.env.example` documents `DATABASE_URL` as a required variable with a placeholder value; the real value is never checked in.
- Phase 1's "Backend can reach PostgreSQL" verification criterion is satisfied via the backend's dependency-health check against the real Neon branch, not a local container's health check.
- Phase 4 (Database and repository foundation) runs Alembic migrations against this same Neon branch.

## Reversal Conditions

If a concrete, demonstrated need for fully offline development arises, a local Postgres container may be added for dev-only use via a new ADR, without changing that Neon remains the sole system of record for any shared or deployed environment.
