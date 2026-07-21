Version: 1.0
Status: DRAFT
Owner: Echo Project (Approvals Domain)
Last Updated: July 2026

# Approval Model

## Purpose

This document defines the concrete Approval Proposal schema, state machine, and execution-authorization rules referenced by CONSTITUTION.md's Approval Principle and required by PROMPT.md Section 11. It is normative for the Approvals domain (DOMAIN_OWNERSHIP.md) and for every write-capable domain that submits proposals to it. No domain may implement its own approval or execution logic — see ADR_0003.

## Action Proposal

Every consequential operation first creates an immutable Action Proposal with the following fields:

| Field | Description |
|---|---|
| `proposal_id` | stable identifier |
| `user_id` | proposing on behalf of which user |
| `action_type` | e.g. `calendar.create_event`, `gmail.send_message` |
| `action_schema_version` | version of the payload schema |
| `summary` | human readable summary |
| `payload` | full normalized payload — the exact data that will be executed |
| `target_system` | external system the action affects |
| `expected_effect` | what will change externally |
| `risk_level` | e.g. low / medium / high |
| `required_permission` | permission needed to approve |
| `created_at` | creation time (UTC, via the clock abstraction — see DATA_MODEL.md) |
| `expires_at` | expiration time |
| `created_by` | proposal creator (always the system, on behalf of a user request — never the assistant approving itself) |
| `validation_result` | pass/fail plus details |
| `warnings` | non-blocking issues surfaced to the reviewer |
| `source_context` | correlation id, originating conversation/request |
| `payload_hash` | hash of `payload` — see Approval Binding |
| `status` | current state — see State Machine |

The payload is normalized and complete: the execution stage never accepts a raw payload from the model at execution time, only a reference to this stored, immutable proposal (Execution Separation, below).

## State Machine

States: `draft`, `validated`, `awaiting_approval`, `approved`, `rejected`, `expired`, `executing`, `executed`, `verification_failed`, `execution_failed`, `cancelled`.

Allowed transitions:

```text
draft              -> validated | cancelled
validated          -> awaiting_approval | cancelled
awaiting_approval   -> approved | rejected | expired | cancelled
approved           -> executing | expired | cancelled
executing          -> executed | execution_failed
executed           -> verification_failed        (post-execution verification did not confirm the effect)
```

Every other transition is invalid and must be rejected in code, not merely discouraged by convention. `rejected`, `expired`, `cancelled`, `execution_failed`, and `verification_failed` are terminal for that proposal — a corrected action creates a *new* proposal with a new `proposal_id`, it does not resurrect the old one (consistent with the Constitution's Immutable Records principle: corrections produce new records, not modifications).

## Approval Binding

An approval record binds to:

1. `proposal_id`
2. `payload_hash` (hash of the exact payload at approval time)
3. `user_id` (the approving user — always a human; the assistant can never be the approver)
4. `approved_at`
5. `approval_expires_at`
6. optional confirmation challenge, required for `risk_level: high` actions

**Before execution**, the Approval Engine re-hashes the payload currently attached to the proposal and compares it to the `payload_hash` recorded at approval time. Any material edit after approval changes the hash, which invalidates the prior approval and forces a new `awaiting_approval` cycle. This is enforced in code, not by UI convention.

## Execution Separation

Proposal creation and action execution are separate capabilities with separate contracts (CAPABILITY_REGISTRY.md):

- The **proposal-creation capability** may be invoked by the Capability Planner (i.e., a model-proposed plan may create a proposal).
- The **execution capability** accepts only an *approved proposal id* — never a raw payload. The execution service loads the immutable stored payload itself. A model cannot supply or alter what gets executed at execution time.
- The Capability Planner and any language model are never permitted to call the execution capability directly without the Approval Checker stage (REQUEST_LIFECYCLE.md) having independently confirmed a valid, matching, unexpired approval exists.

A user message such as "send this now" may authorize *creating* a proposal (and, if the review UI is presented and approved in the same turn, an approval) but never bypasses the review object and the approval-binding check above.

## Idempotency

Every execution carries an idempotency key derived from `proposal_id` (one proposal executes at most once). Retries of a failed execution attempt must not create duplicate external effects (duplicate calendar events, duplicate sent emails, duplicate transfers). The execution adapter is responsible for using the target system's own idempotency mechanism where available, and for detecting "already applied" states otherwise.

## Verification

After execution, the Execution Verifier stage (REQUEST_LIFECYCLE.md) re-queries the external system to confirm the effect actually occurred — for example, re-fetching the created Google Calendar event by id, or confirming a Gmail message id and its sent state. A `200`-level HTTP response from the provider is not sufficient evidence of success. If verification cannot confirm the effect, the proposal moves to `verification_failed`, which is surfaced to the user distinctly from `executed`.

## Self-Approval Prohibition

The system that creates a proposal (the assistant, the orchestrator, or any automated trigger) can never also record the approval for that proposal. Approval always requires a human-originated action captured through the review interface. This is enforced structurally: the approval-recording capability requires an authenticated human user context and rejects any request originating from the same execution context that created the proposal.

## Applicability

This model is shared platform logic in the Approvals domain (ADR_0003). Calendar (Phase 11) and Email (Phase 21) are the first two domains to submit proposals against it; every future write-capable domain (including any future trading capability) uses the same schema, state machine, and execution pipeline without domain-specific variants.
