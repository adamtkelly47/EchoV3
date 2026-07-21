Version: 1.0
Status: DRAFT
Owner: Echo Project (Capabilities Domain)
Last Updated: July 2026

# Capability Registry

## Purpose

This document defines the capability contract and registry behavior referenced by CONSTITUTION.md's Capability First Architecture and required by PROMPT.md Section 10. The Capability Registry is the single mechanism through which any executable behavior becomes available to the Capability Planner (REQUEST_LIFECYCLE.md) — there are no keyword lists, prompt instructions, or hardcoded routing tables.

## What Must Be Registered

Every user-facing, model-selectable, scheduled, automated, or externally invokable business capability must exist in the registry. Internal implementation methods, repositories, migrations, startup routines, and health checks are not capabilities unless intentionally exposed through the application boundary.

## Capability Contract

A capability is not registered unless every field below is defined:

| Field | Description |
|---|---|
| `capability_id` | unique identifier, e.g. `calendar.search_events` |
| `version` | capability schema version |
| `display_name` | human-readable name |
| `description` | what it does, in user-facing language |
| `owner` | owning domain (must match DOMAIN_OWNERSHIP.md) |
| `input_schema` | typed schema for inputs |
| `output_schema` | typed schema for outputs |
| `permission_requirements` | what permission the caller must hold |
| `execution_environment` | e.g. request-time (backend) or job (worker) |
| `read_write_classification` | exactly one of `read` or `write` — see below |
| `approval_requirement` | none, or a reference to the Approval Model's proposal type |
| `timeout` | maximum execution duration |
| `retry_policy` | deterministic retry behavior |
| `idempotency_behavior` | how repeated invocation is handled |
| `provenance_requirements` | what provenance the capability must attach to its output |
| `supported_interfaces` | which interfaces may invoke it (in practice: all, per Interface Parity) |
| `expected_errors` | the error taxonomy entries (see below) it may raise |

## Read/Write Classification

Every capability is exactly one of:

- **Read** — never modifies external state.
- **Write** — may modify external state, and only through the Approval Engine (APPROVAL_MODEL.md).

Mixed capabilities (a single capability that both reads and writes) are prohibited. A workflow needing both composes two capabilities — e.g. `calendar.propose_create_event` (write, approval-gated proposal creation) is distinct from `calendar.search_events` (read).

## Discovery

Capabilities are discovered exclusively through registration — never through keyword lists, prompt instructions, manual routing tables, string matching, or hardcoded conditionals. The registry is the single source of truth for what Echo can do at any point in time.

## Execution Pipeline

Every capability invocation follows the same sequence, matching CONSTITUTION.md's Capability Execution section and REQUEST_LIFECYCLE.md's Capability Executor stage:

```text
Capability requested -> Registry lookup -> Input validation -> Permission check
  -> Approval check (write capabilities only) -> Execution -> Output validation
  -> Provenance recording -> Audit recording
```

Invalid input never reaches a provider. A capability without the required permission never executes. A write capability without a valid, matching, unexpired approval never executes (APPROVAL_MODEL.md).

## Example Categories (illustrative, not exhaustive)

Read current time; search calendar; read portfolio positions; calculate allocation; search email; research a security; draft an email proposal (write, creates a proposal); propose a calendar event (write, creates a proposal); execute an approved calendar event (write, requires approval); send an approved email (write, requires approval).

## Ownership

The registry itself (metadata, versioning, discovery, permission/approval requirement declarations) is owned by the Capabilities domain. The Capabilities domain does not execute capabilities — it describes them. Execution is owned by the Capability Executor stage, invoking each capability's actual implementation inside its owning domain.

## Phase Applicability

Phase 5 (Capability Registry and Tool Execution) implements this contract for read capabilities with fake test capabilities. Every subsequent phase that introduces a new capability (Calendar reads in Phase 10, Calendar writes in Phase 11, Schwab reads in Phase 12, and so on) registers against this same contract — no phase introduces a parallel or simplified registration mechanism.
