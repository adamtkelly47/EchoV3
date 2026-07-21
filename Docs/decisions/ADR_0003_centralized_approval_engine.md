Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0003: Centralized Approval Engine for All Consequential Writes

## Context

CONSTITUTION.md's Approval Principle and PROMPT.md Section 3.3 require every consequential external action (send, write, delete, modify, transfer, schedule, cancel) to follow one identical lifecycle: propose, validate, review, approve, execute, verify, audit — with no exceptions and no self-approval by the assistant.

## Decision

A single Approval Engine, owned by the Approvals domain, owns proposal creation, the proposal state machine (see APPROVAL_MODEL.md), payload hashing and binding, expiration, and execution authorization for every write-capable domain (Calendar, Email, and any future write-capable domain). Every write capability across every domain invokes the same execution pipeline: validate → check approval → load the immutable approved payload → invoke the execution adapter → verify the external result → record audit. Individual domains do not implement their own execution or approval logic.

## Alternatives Considered

**Per-domain approval logic** (each domain implements its own review/execute flow). Rejected — CONSTITUTION.md explicitly lists "Approval rules copied across domains" as a prohibited duplicate business rule, and the Constitution states execution ownership belongs solely to the Approval Engine.

**A bypass path for "trusted" or low-risk actions.** Rejected — CONSTITUTION.md states "There shall be no exceptions" for the approval lifecycle.

## Consequences

- No write capability may ship in any domain until the Approval Engine (Phase 6) exists, is tested, and demonstrates: execution without approval fails, self-approval is impossible, approval binds to an exact payload hash, editing invalidates approval, expired approval fails, and duplicate execution is prevented.
- Every write-capable domain's proposal payload is domain-specific, but the state machine, hashing, and execution pipeline are shared platform code, not domain code.

## Reversal Conditions

None within v1 scope. This is a Constitutional invariant, not a reversible implementation choice — changing it requires a Constitutional amendment, not merely a new ADR.
