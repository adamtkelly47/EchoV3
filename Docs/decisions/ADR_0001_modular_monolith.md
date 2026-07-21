Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0001: Modular Monolith With Isolated Execution Roles

## Context

This is the third attempt at building Echo. Prior attempts became disorganized, overly coupled, and hard to reason about. PROMPT.md Section 4 mandates a small number of operationally justified containers rather than a microservice-per-feature architecture, while still separating request handling from long-running work.

## Decision

Echo ships as one Python codebase (`echo/`) with three runtime entrypoints — `apps/api`, `apps/worker`, `apps/scheduler` — sharing the same `core/`, `domains/`, `providers/`, and `infrastructure/` modules. No domain is extracted into an independently deployable service at this time.

The backend handles request/response and approval-gated orchestration. The worker handles asynchronous, retryable, or long-running jobs. The scheduler creates jobs on a cadence but never performs domain work or executes consequential actions itself.

## Alternatives Considered

**Microservices per domain.** Rejected: operational overhead, cross-service transactional complexity, and no measurable requirement justifying it yet. This is exactly the "Premature Distribution" anti-pattern the Constitution prohibits.

**Single process, no worker/scheduler separation.** Rejected: long-running work (research ingestion, embeddings, snapshot jobs) would block request handlers, violating the Background Work principle ("Long-running work should execute outside request lifecycles whenever practical").

## Consequences

- Deployment is simple: one image, three entrypoints, shared migrations.
- Transactional consistency is available via a single database.
- Because there is no process boundary forcing domain isolation, automated architecture tests (forbidden imports, dependency direction) are mandatory rather than optional — the modular monolith only stays modular if tooling enforces it.

## Reversal Conditions

A domain may be extracted into its own service only when justified by measurable operational requirements (demonstrated scale, deployment cadence, security isolation) — never because the domain exists or because extraction is technically possible, per the Constitution's Modular Monolith Principle.
