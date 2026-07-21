Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0002: Neon PostgreSQL as Sole System of Record

## Context

PROMPT.md Section 5.5 requires Neon serverless Postgres to hold all durable state (23 listed categories including users, conversations, portfolio snapshots, research entities, memory records, approval proposals, and audit events) and explicitly prohibits using a vector database as the system of record.

## Decision

Neon Postgres is the sole durable system of record for all state owned by every domain, per the State Ownership Matrix in DOMAIN_OWNERSHIP.md. Semantic search (memory retrieval, research similarity) uses PostgreSQL's vector capabilities (e.g. pgvector) as an index over these authoritative records, never as the record itself. Redis is used only for ephemeral and coordination workloads (job queue transport, distributed locks, rate limiting, short-lived caches, streaming partial responses, event notifications, scheduler coordination) and must never become the sole home of durable user data.

## Alternatives Considered

**A dedicated vector database (e.g. a managed vector store).** Rejected for now under the Simplicity Principle and Provider Due Diligence — no measured requirement yet demonstrates pgvector is insufficient. May be reconsidered via ADR if scale or query-latency evidence justifies it.

**Redis as a durable store for any domain state.** Rejected — violates the Persistence Philosophy ("Caching is never a source of truth. The system should function correctly with caching disabled.").

## Consequences

- All repositories live under `infrastructure/database/`, using one migration framework (Alembic) and one set of transaction boundaries.
- Memory and research semantic retrieval (Phase 9, Phase 16+) are built on pgvector against Postgres-resident records, not a separate store.
- Every domain's repository ownership (per DOMAIN_OWNERSHIP.md) maps 1:1 to Postgres tables/schemas owned by that domain's repository layer.

## Reversal Conditions

Introduce a dedicated vector store only with measured evidence of pgvector performance or scale limits under real Echo workloads, documented in a new ADR.
