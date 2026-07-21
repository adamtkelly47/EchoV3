Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Data Model (Conceptual)

## Purpose

This document defines Echo's durable state categories conceptually, mapped to their owning domain, and the provenance model that makes every externally derived or computed value traceable. Per PROMPT.md Section 32 item 9, this is conceptual only — no Alembic migrations exist yet. Migrations begin in Phase 4.

## Authoritative Store

Per ADR_0002, Neon Postgres is the sole system of record. Every category below has exactly one owning domain, matching the State Ownership Matrix in DOMAIN_OWNERSHIP.md. No category is duplicated across domains.

## State Categories

| Category (PROMPT.md 5.5) | Owning Domain |
|---|---|
| Users | Identity |
| Conversations | Conversation |
| Messages | Conversation |
| Model calls | System (cross-cutting observability of model gateway usage; see note below) |
| Tool calls | Capabilities (execution audit) |
| Source records | owned by whichever domain the sourced data belongs to (provenance is attached, not separately owned — see Provenance Model) |
| Integrations | Identity (Connected Accounts, Provider Configuration) |
| Credentials metadata | Identity |
| Account metadata | Portfolio |
| Portfolio snapshots | Portfolio |
| Holdings snapshots | Portfolio |
| Calendar event cache | Calendar |
| Email metadata cache | Email |
| Research entities | Research |
| Documents | Knowledge (general reference); Research (research-specific filings/reports) — see ADR_0005 |
| Memory records | Memory |
| Approval proposals | Approvals |
| Approval decisions | Approvals |
| Action executions | Approvals (Execution Ownership) |
| Audit events | System, with per-domain audit detail recorded by the acting domain |
| Jobs | System (job/queue metadata is operational state, not business state) |
| Notifications | Notifications |
| IPS documents and rule definitions | Portfolio |

**Note on "Model calls":** model-gateway usage (latency, token counts, cost estimates, escalation decisions) is operational telemetry about the platform, not a business concept belonging to any product domain — it is owned by System, consistent with System's ownership of "Telemetry" and "Metrics." Individual domains that trigger a model call (e.g. Research requesting a local classification) reference the model-call record by id; they do not own it.

**Note on "Tool calls":** capability invocation records (which capability ran, with what inputs/outputs, permission and approval checks) are owned by Capabilities, consistent with its ownership of "Capability Health Metadata" and the Constitution's requirement that capability execution be auditable at the platform level, independent of which domain the capability belongs to.

Every category has exactly one authoritative owner per the table above. If implementation reveals a category that appears to need two owners, that is an architecture defect per DOMAIN_OWNERSHIP.md's Ownership Violations section, and must be resolved via ADR before proceeding — not by writing to the same table from two domains.

## Provenance Model

Per CONSTITUTION.md's Provenance section and PROMPT.md Section 14, every normalized object derived from an external system is connectable to one or more source records, and every computed value records its inputs.

### Source Record

| Field | Description |
|---|---|
| `source_type` | e.g. brokerage-api, calendar-api, filing, news-article |
| `provider` | e.g. schwab, google-calendar, sec-edgar |
| `retrieved_at` | UTC retrieval time, from the clock abstraction |
| `origin` | original endpoint or document reference |
| `external_id` | the record's identifier in the source system |
| `request_params` | parameters used for retrieval (redacted of secrets) |
| `response_hash` | content hash of the raw response |
| `data_effective_at` | the time the data itself represents, which may differ from `retrieved_at` |
| `freshness_policy` | how long this record is considered current |
| `raw_storage_ref` | pointer to permitted raw payload storage, when retained |
| `parser_version` | version of the normalization logic used |
| `validation_status` | passed / failed / partial |
| `error_state` | populated on partial or failed normalization |

### Computed Value Record

| Field | Description |
|---|---|
| `calculation_name` | e.g. `portfolio.total_market_value` |
| `calculation_version` | version of the deterministic calculation code |
| `input_record_ids` | identifiers of every source or upstream computed record used |
| `executed_at` | UTC execution time |
| `output` | the computed value |
| `rounding_policy` | explicit rounding rule applied |
| `validation_result` | pass/fail against any sanity checks |

This structure lets Echo answer "where did that number come from?" for any user-facing figure: follow the computed-value record's `input_record_ids` back to source records, and each source record back to a specific provider call at a specific time.

### Negative and Missing Data

When a value cannot be retrieved or computed, no record is fabricated. The absence is represented explicitly (missing cost basis stays missing; it is never estimated to "fill in" a gain/loss calculation), consistent with the Constitution's Verified Truth and Negative Verification principles.

## Immutability

Portfolio snapshots, research evidence, audit events, execution history, conversation history, and approval history are immutable once written. Corrections and updates produce new, superseding records rather than mutating history in place, per the Constitution's Immutable Records principle.

## Vector Search

Semantic retrieval (memory ranking, research similarity) is implemented using PostgreSQL's vector capabilities over the authoritative tables above. The vector index is derived data, not a separate source of truth — it can be rebuilt from the authoritative records at any time (ADR_0002).
