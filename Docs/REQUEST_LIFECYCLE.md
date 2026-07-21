Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Request Lifecycle

## Purpose

This document expands CONSTITUTION.md's Request Execution Pipeline into concrete stage contracts: what each stage receives, what it owns, what it produces, and which component is responsible for it. It applies to every interface (chat, dashboard, CLI, future voice/mobile) and to scheduled/automated work, per the Interface Parity principle.

This document supersedes the empty, misnamed `REQUEST_LIFESTYLE.md`, which has been removed.

## Relationship to Other Documents

CONSTITUTION.md defines the pipeline's existence and ordering as architectural law. This document defines the concrete contract of each stage. CAPABILITY_REGISTRY.md defines what a capability is. APPROVAL_MODEL.md defines the approval sub-lifecycle referenced at the Approval Checker stage.

---

## Pipeline Stages

```text
User Request
  -> Intent Builder
  -> Context Builder
  -> Capability Planner
  -> Approval Checker
  -> Capability Executor
  -> Execution Verifier
  -> Evidence Collector
  -> Response Generator
  -> Persistence
  -> Audit
```

Every stage receives and propagates a **correlation identifier** established at the moment the request enters the system (API route, worker job pickup, or scheduler trigger).

### 1. Intent Builder

**Input:** raw user message or triggering event, conversation context reference, correlation id.

**Owns:** determining *what* the user (or scheduled trigger) is attempting to accomplish.

**Does not own:** deciding *how* the request executes, which capabilities are needed, or whether the request is permitted.

**Output:** a structured, descriptive intent object. Intent is descriptive, never executable — it must not contain capability identifiers chosen by the model.

### 2. Context Builder

**Input:** intent object, user identifier, correlation id.

**Owns:** deterministic assembly of the information required to reason about the request: recent conversation, durable memory, active projects, relevant portfolio/calendar/research state, user preferences.

**Output:** a typed context package. Context assembly must remain deterministic wherever possible — retrieval ranking and filtering are code, not model judgment.

### 3. Capability Planner

**Input:** intent object, context package.

**Owns:** selecting zero, one, or multiple *registered* capabilities from the Capability Registry required to satisfy the intent. A language model may propose a plan using registered capabilities only.

**Does not own:** capability authorization, permission checks, or approval — those belong to the Approval Checker. The planner may never invent a capability that is not registered.

**Output:** a candidate execution plan referencing capability identifiers and versions.

### 4. Approval Checker

**Input:** candidate execution plan.

**Owns:** deterministic evaluation of permission requirements, approval requirements, proposal validity, proposal expiration, approval binding, and execution authorization, per APPROVAL_MODEL.md. This stage is pure deterministic code — models do not determine approval.

**Output:** an authorized execution plan (read capabilities cleared to run immediately; write capabilities either blocked pending a new approval proposal, or cleared because a valid, matching, unexpired approval already exists).

### 5. Capability Executor

**Input:** authorized execution plan.

**Owns:** invoking registered capabilities through their contracts (CAPABILITY_REGISTRY.md). Execution never bypasses validation, permissions, approval, audit, or provenance.

**Output:** raw capability results (provider data, computed values, or write-execution results with idempotency keys).

### 6. Execution Verifier

**Input:** raw capability results.

**Owns:** for write operations, confirming the external system actually reflects the intended change (e.g. re-querying Google Calendar for the created event) rather than trusting a 200-status response. For read operations, this stage confirms schema/output validation succeeded.

**Output:** verified results with a verification status (verified, verification failed, verification skipped-not-applicable).

### 7. Evidence Collector

**Input:** verified results.

**Owns:** assembling provider results, calculations, citations, provenance, verification status, confidence, and any missing-information flags into an evidence package. Evidence is collected before response generation — the Response Generator consumes evidence, it does not create it.

**Output:** an evidence package.

### 8. Response Generator

**Input:** evidence package, intent, context.

**Owns:** synthesis, explanation, clarification, reasoning, recommendations for the user-facing response. Must never invent missing evidence; must state explicitly when information could not be verified (per the Constitution's Negative Verification rule).

**Output:** the user-facing response (streamed or complete).

### 9. Persistence

**Input:** the full record of the request: messages, tool calls, model calls, memory updates, approval records.

**Owns:** durable storage of the interaction per each domain's repository ownership (DOMAIN_OWNERSHIP.md). Only durable information is persisted — transient execution state stays out of persistent storage.

### 10. Audit

**Input:** the completed request record.

**Owns:** an immutable audit entry: correlation id, timestamp, capabilities used, provider interactions, approval references, execution result, verification status. Audit is mandatory for every significant request and is never skipped, per the Constitution's Audit Philosophy.

---

## Communication Map

This is the concrete component-to-component path referenced by the pipeline above, per PROMPT.md Section 6:

```text
User interface -> Backend API
Backend API -> Application orchestration layer (runs the pipeline above)
Application orchestration layer -> Domain services
Domain services -> Integration adapters (providers/) or repositories
Integration adapters -> External systems
Repositories -> Neon Postgres
Long-running work -> Redis queue -> Worker
Worker -> Domain services and provider adapters
Worker -> Ollama, when local inference is appropriate
Backend -> Claude, through the model gateway, when hosted reasoning is justified
```

All significant operations emit structured audit events (Stage 10). Internal communication within the codebase uses typed Python interfaces and domain objects. External and asynchronous boundaries (jobs, events, API responses) use versioned, typed schemas — arbitrary dictionaries never cross a module boundary where a typed model can be defined, per the Constitution's Typed Contracts rule.

## Applicability

This pipeline governs chat, dashboard actions, CLI development tools, and future mobile/voice interfaces identically (Interface Parity, Section 3.5). It also governs scheduler-triggered work: the Scheduler creates a job: the job still enters the pipeline at the Capability Planner/Executor stages under the same authorization and audit rules as a user-initiated request. No interface or trigger source may introduce an alternative execution path.
