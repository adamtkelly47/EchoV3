Version: 1.0 (Architecture Freeze)
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

Normative Language

The keywords MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY, and OPTIONAL are to be interpreted as normative requirement levels.

MUST / SHALL indicate mandatory architectural requirements.

SHOULD indicates the preferred architectural default.

MAY indicates an optional implementation choice.

Echo Constitution
Purpose

This document is the governing engineering constitution for the Echo Personal AI Operating System.

It defines architectural principles that are intended to remain stable throughout the lifetime of the project.

This document does not describe implementation details.

This document defines:

system philosophy
engineering principles
architectural constraints
ownership rules
governance rules
nonnegotiable invariants

Every future implementation decision must remain consistent with this constitution unless explicitly superseded through the Architecture Decision Record (ADR) process.

If implementation and this constitution disagree, the constitution takes precedence.

Constitutional Status

This document is considered the highest authority within the repository.

No lower-level document may redefine architecture established by a higher-authority document. It may only elaborate, constrain, or implement it.

Priority order:

User Authority and Safety Constraints

↓

Echo Constitution

↓

Approved Architecture Decision Records

↓

Architecture Specifications

↓

Executable Tests and Architectural Enforcement

↓

Implementation

No implementation may intentionally violate this constitution.

Phase Completion

A phase is not considered complete until its required verification has successfully passed.

Verification SHALL include all checks applicable to that phase, including architectural validation, testing, type checking, formatting, linting, and relevant security verification where applicable.

Verification shall be based on actual command results rather than assumption or assertion.

Failed verification SHALL be diagnosed and resolved before the phase is considered complete.

Implementation phases SHALL remain focused on their stated objectives and shall not include unrelated cleanup or combine multiple major phases without explicit justification.

Scope

This constitution governs every repository within the Echo project including future repositories unless explicitly documented otherwise.

It applies to:

backend
frontend
worker
scheduler
infrastructure
providers
domains
documentation
testing
deployment
future interfaces
Product Mission

Echo exists to become a trusted personal operating system rather than a chatbot.

Echo should continuously assist the user by understanding:

projects
finances
communications
schedule
goals
preferences
long term plans
historical decisions

Echo should reduce cognitive load while improving decision quality.

Echo should never replace human judgment.

Echo should improve human judgment.

Product Definition

Echo is intended to become:

a conversational assistant
a personal operating system
a decision support platform
a research platform
an orchestration platform
a memory system
an automation platform
a planning partner

Echo is not intended to become:

a generic chatbot wrapper
an autonomous agent
a financial trading bot
a dashboard with disconnected widgets
a prompt collection
a collection of isolated AI agents
a system where the language model owns business logic
Core Philosophy

The project optimizes for long term correctness rather than rapid feature accumulation.

Every feature must satisfy five questions.

1. Is it understandable?

A competent software engineer unfamiliar with Echo should be able to determine:

ownership
execution path
responsibilities
dependencies
data flow

without reverse engineering the repository.

2. Is it testable?

Every important behavior should be independently testable.

Behavior that cannot be tested SHOULD be treated as an architectural smell and requires documented justification.

3. Is it replaceable?

External vendors are temporary.

Echo architecture is permanent.

Every provider must be replaceable.

4. Is it traceable?

Every significant system behavior should answer:

Where did this come from?

Why did this happen?

Who initiated it?

What changed?

When did it happen?

5. Is it safe?

The system should make unsafe behavior difficult rather than relying on developer discipline.

Safety should emerge from architecture.

Engineering Values

Echo prioritizes the following values in descending order.

Correctness
Safety
Maintainability
Clarity
Determinism
Replaceability
Testability
Observability
Performance
Cost

Feature count is never considered an engineering value.

Long Term Design Principles

Echo shall remain:

modular
deterministic
observable
provider independent
interface independent
evidence based
provenance aware
approval gated
event oriented
documentation first
Repository Governance

Architecture precedes implementation.

Documentation precedes implementation.

Testing precedes optimization.

Correctness precedes convenience.

Architectural Freeze

Phase 0 establishes the architectural foundation.

After Phase 0 is approved:

Major architectural changes require an ADR before implementation.

Architecture shall not evolve implicitly through code.

Architecture Decision Records

Architecture Decision Records are mandatory.

An ADR MUST exist before implementing changes affecting:

module ownership
dependency direction
provider interfaces
persistence model
approval architecture
orchestration
security model
application architecture
repository structure
capability routing
model routing

Implementation without an approved ADR is prohibited.

Repository Evolution

Echo evolves through vertical slices.

Each phase must be independently complete.

No phase may depend on partially implemented future work.

No Future Scaffolding Rule

Echo SHALL NOT create code, folders, abstractions, interfaces, repositories, services, providers, modules, packages, or documentation solely because they may be needed in a future phase.

A phase may create only the artifacts required for that phase.

Examples of prohibited behavior:

Creating empty providers for future integrations.

Creating unused repositories.

Creating placeholder services.

Creating speculative abstractions.

Creating empty interfaces.

Creating future database models.

Creating empty folders for future capabilities.

Every artifact introduced into the repository must have an active responsibility during its implementation phase.

Simplicity Principle

Echo prefers the smallest architecture capable of solving today's problem while preserving tomorrow's extension points.

Small today.

Expandable tomorrow.

Modular Monolith Principle

Echo shall begin as a modular monolith.

Not because microservices are bad.

Because unnecessary distributed systems are worse.

Modules shall remain internally cohesive.

Extraction into independent services shall occur only when justified by measurable operational requirements.

Never because a module merely exists.

Container Philosophy

Deployment units are not ownership boundaries.

Execution environments are not domain boundaries.

Containers exist because of runtime requirements.

Modules exist because of business ownership.

Separation of Concerns

Echo separates responsibilities into distinct layers.

Presentation.

Application.

Domain.

Infrastructure.

Providers.

Persistence.

Each layer has different responsibilities.

Each layer has different rules.

No layer may absorb the responsibilities of another.

Interface Independence

Every user interface must invoke identical backend capabilities.

Chat.

Dashboard.

Voice.

Mobile.

API.

Automation.

Future interfaces.

No interface may implement unique business logic.

Provider Independence

Providers are implementation details.

Echo's domain and application architecture shall never depend upon vendor-specific implementations.

Infrastructure technologies such as PostgreSQL and Redis MAY be selected as implementation choices, but business logic SHALL remain isolated from storage-specific behavior.

Domain behavior shall never depend directly upon provider SDKs, storage engines, transport implementations, or vendor-specific APIs.

Examples include:

Schwab.

Google.

Claude.

Ollama.

Redis.

PostgreSQL.

Any provider may be replaced.

Domain behavior shall remain unchanged.

Model Independence

Language models are interchangeable reasoning providers.

The system shall never assume:

Claude specific behavior.

OpenAI specific behavior.

Ollama specific behavior.

Vendor prompts shall remain inside provider adapters.

Deterministic Computation

Language models shall not perform authoritative computation.

Deterministic code owns:

Arithmetic.

Portfolio calculations.

Date calculations.

Rule evaluation.

Threshold checks.

Reconciliation.

Financial metrics.

Performance calculations.

State transitions.

Permission checks.

Language models may explain results.

They may not define results.

Verified Truth

Echo must distinguish between:

Verified facts.

Inferred conclusions.

Candidate observations.

Hypotheses.

Opinions.

Suggestions.

Every externally derived fact shall have provenance.

Every unsupported statement shall be identified as unsupported.

Negative Verification

Negative claims require verification.

Echo must not state:

"It doesn't exist."

"It isn't available."

"You don't have one."

"It cannot be found."

unless the appropriate source has been queried when verification is possible.

Evidence First

Evidence precedes interpretation.

Collection precedes synthesis.

Normalization precedes reasoning.

Reasoning never replaces missing evidence.

Provenance

Every externally derived value must remain traceable.

Every computed value must remain reproducible.

Every recommendation should identify its supporting evidence.

Every calculation should identify its inputs.

Human Authority

Humans remain the final decision makers.

Echo recommends.

Echo explains.

Echo warns.

Echo proposes.

Echo never assumes authority over consequential decisions.

Approval Principle

Every consequential action follows the same lifecycle.

Proposal.

Validation.

Human review.

Approval.

Execution.

Verification.

Audit.

There shall be no exceptions.

Echo shall never approve its own proposals.

Every approval SHALL bind to a specific immutable proposal payload and its payload hash.

Any material modification to an approved proposal SHALL invalidate the previous approval and require a new approval.

Approvals are single-use unless explicitly documented otherwise.

Expired approvals SHALL NOT execute.

Before execution, the Approval Engine SHALL verify that the approved payload exactly matches the payload being executed.

Read Before Write

Every integration begins as read only.

Write capabilities require:

stable read behavior

approval engine integration

verification

auditing

minimal permissions

documented scope

No write capability may precede its corresponding read capability.

Execution Ownership

Consequential execution is owned by the Approval Engine.

Individual domains SHALL NOT implement independent execution flows.

The Approval Engine is responsible for:

validating proposals

checking approval

loading immutable payloads

invoking execution adapters

performing verification

recording audit events

maintaining idempotency

All write capable domains use the same execution pipeline.

# Layered Architecture

Echo SHALL be organized into explicit architectural layers.

Each layer has a single purpose.

Each layer owns specific responsibilities.

Each layer exposes stable interfaces.

Each layer has strict dependency rules.

---

# Architectural Layers

```text
Frontend

↓

API

↓

Application

↓

Domains

↓

Domain Interfaces

↓

Providers / Infrastructure

↓

External Systems
```

This dependency direction is absolute.

No layer may import a layer above itself.

No layer may bypass intermediate ownership.

---

# Dependency Hierarchy

Echo enforces a strict one way dependency model.

Allowed direction:

```text
Frontend

↓

API

↓

Application

↓

Domains

↓

Interfaces

↓

Providers / Infrastructure

↓

External Systems
```

Forbidden:

* upward imports
* circular imports
* hidden dependencies
* direct cross-domain imports

Peer modules within the same bounded context MAY collaborate through explicit internal contracts.

Cross-domain collaboration SHALL occur through the Application layer or versioned domain events.

Examples:

Allowed:

Application imports Portfolio Domain.

Portfolio Domain imports Portfolio Interface.

Schwab Provider implements Portfolio Interface.

Forbidden:

Portfolio Domain imports Gmail Domain.

Portfolio Domain imports Calendar Domain.

Portfolio Domain imports FastAPI.

Portfolio Domain imports SQLAlchemy session directly.

Frontend imports Providers.

API imports Schwab SDK.

---

# Layer Responsibilities

## Frontend

Owns:

* rendering
* user interaction
* presentation
* accessibility
* visualization
* streaming UI

Must never own:

* business logic
* authorization rules
* calculations
* orchestration
* provider calls

---

## API

Owns:

* HTTP endpoints
* request validation
* authentication
* response serialization
* streaming transport

Must never own:

* business rules
* orchestration
* provider logic
* calculations

API routes should remain intentionally thin.

---

## Application Layer

The Application layer coordinates work spanning multiple domains.

It is the only layer permitted to coordinate more than one domain simultaneously.

Application owns:

* workflows
* orchestration
* capability execution
* request pipeline
* command handling
* query handling
* cross domain coordination
* approval coordination

Application never owns business rules belonging to individual domains.

---

# Application Structure

```text
application/

    capabilities/

    orchestrators/

    workflows/

    commands/

    queries/
```

Responsibilities:

## capabilities

Expose executable platform capabilities.

## orchestrators

Coordinate complete request execution.

## workflows

Coordinate multiple domains.

## commands

Perform state changing operations.

## queries

Perform read operations.

---

# Domain Layer

Domains own business behavior.

Each domain represents one business capability.

A domain should remain internally cohesive.

Domains must not coordinate other domains.

Domains should not know other domains exist.

---

# Domain Structure

Every domain should follow a consistent internal structure whenever applicable.

```text
domain/

    models.py

    schemas.py

    policies.py

    service.py

    repository.py

    interfaces.py

    events.py

    errors.py
```

Additional files may exist only when justified.

---

# Domain Responsibilities

Each domain explicitly separates three responsibilities.

## Policy

Policies make decisions.

Policies answer questions like:

Can this happen?

Should this happen?

Is this allowed?

Does this violate a rule?

Policies never persist data.

Policies never coordinate workflows.

---

## Service

Services coordinate work inside one domain.

Services call:

repositories

policies

domain models

events

Services never own business rules that belong inside policies.

Services never coordinate multiple domains.

---

## Repository

Repositories own persistence.

Repositories:

load

save

query

delete

Repositories never contain business logic.

Repositories never make decisions.

Repositories never orchestrate workflows.

---

# Aggregate Ownership

Every aggregate root owns its own invariants.

Callers must not enforce aggregate correctness.

Examples:

ApprovalProposal owns:

* immutable payload
* payload hash
* valid transitions
* expiration
* approval binding
* state validity

MemoryRecord owns:

* confidence bounds
* supersession rules
* review requirements

PortfolioSnapshot owns:

* immutability
* timestamp consistency
* provenance linkage

Invalid aggregate states must be impossible to construct.

---

# Shared Module Rule

Generic shared directories are prohibited.

Examples:

```text
shared/

common/

helpers/

misc/

utilities/
```

may not be created without an Architecture Decision Record.

An ADR must justify why the responsibility cannot belong to:

* a domain
* the application layer
* infrastructure
* providers
* core platform

Convenience alone is not sufficient justification.

---

# Core Platform

Reusable platform functionality belongs inside Core.

Examples:

configuration

logging

security

clock

identifiers

provenance

events

observability

Core must remain domain independent.

---

# Providers

Providers translate external systems into Echo contracts.

Providers own:

authentication

SDK usage

HTTP clients

API translation

vendor normalization

retry behavior

rate limit handling

Providers never expose vendor objects outside themselves.

---

# Mandatory Provider Normalization

Normalization is mandatory.

Every provider must convert external objects into normalized Echo objects.

Example:

```text
Schwab Position

↓

NormalizedPosition

↓

Portfolio Domain
```

The Portfolio Domain shall never receive a Schwab SDK object.

Similarly:

```text
Google Event

↓

NormalizedCalendarEvent

↓

Calendar Domain
```

```text
Gmail Message

↓

NormalizedEmail

↓

Email Domain
```

```text
SEC Filing

↓

NormalizedFiling

↓

Research Domain
```

Domains operate exclusively on normalized models.

---

# Typed Contracts

Typed schemas SHALL be used across architectural boundaries.

Provider objects, arbitrary dictionaries, and unvalidated payloads SHALL NOT cross:

API boundaries

Domain boundaries

Provider boundaries

Capability boundaries

Event boundaries

Persistence boundaries

Where a stable contract exists, it SHALL be represented using an explicit typed schema.

---

# Infrastructure

Infrastructure provides platform implementation.

Examples:

database

queue

cache

secret storage

HTTP transport

Infrastructure owns implementation.

Domains own behavior.

---

# External Systems

External systems are considered unreliable.

Echo must assume:

timeouts

schema changes

partial failures

authentication failures

network failures

provider outages

Every provider must tolerate these conditions gracefully.

---

# Repository Structure Principle

Repository organization shall follow business ownership rather than technology.

Prefer:

Portfolio

Calendar

Research

Email

Memory

Identity

rather than:

Models

Controllers

Utilities

Helpers

Services

Architecture should explain business behavior before technical implementation.

---

# Directory Size Discipline

Small directories are easier to understand.

Directories SHOULD normally remain below approximately fifteen files.

Reaching fifteen files SHOULD trigger review.

Exceeding twenty files REQUIRES documented architectural justification.

Possible outcomes:

split the domain

extract a submodule

introduce bounded contexts

create internal packages

Large directories require explicit justification.

---

# File Discipline

Preferred:

under 500 lines

Warning:

800 lines

Strong review:

1,500 lines

Architecture review:

3,000 lines

Soft ceiling:

10,000 lines

No file should approach the ceiling without extraordinary justification.

---

# Function Discipline

Preferred:

under 50 lines

Review:

100 lines

Strong review:

150 lines

Architecture review:

300 lines

Build failure:

500 lines

Large functions indicate missing abstractions.

---

# Complexity Principle

Complexity should exist only when justified by business requirements.

Incidental complexity should be eliminated.

Every abstraction should have a measurable purpose.

Avoid speculative architecture.

---

# Environment Integrity

Mock data, fixture data, sandbox data, staging data, and production data SHALL be clearly distinguished.

Echo SHALL never present simulated or placeholder data as real user data.

Environment boundaries shall remain explicit throughout the platform.

---

# Vertical Slice Development

Echo shall be implemented one complete vertical slice at a time.

Each slice must include:

implementation

tests

documentation

verification

No phase should leave partially completed infrastructure behind.

---

# Phase Discipline

Each implementation phase must:

Restate objectives.

Inspect architecture impact.

Identify affected files.

Implement only required functionality.

Add tests.

Run verification.

Update documentation.

Record risks.

Stop.

No implementation may silently continue into the next phase.

---

# Capability First Architecture

Echo is fundamentally a capability driven system.

The Capability Registry is the central execution mechanism of the platform.

Language models do not execute business logic.

Language models do not invoke providers.

Language models do not choose arbitrary functions.

The only actions available to a model are registered capabilities.

Every executable behavior exposed by Echo shall exist as a capability.

There shall be no hidden execution paths.

---

# Capability Registry

The Capability Registry is a first class platform component.

It is responsible for:

* capability discovery
* capability metadata
* schema registration
* permission requirements
* approval requirements
* execution routing
* timeout policy
* idempotency policy
* provenance requirements
* capability versioning

Every user-facing, model-selectable, scheduled, automated, or externally invokable business capability SHALL exist within the Capability Registry.

Internal implementation methods, repositories, migrations, startup routines, health checks, and infrastructure lifecycle functions are not capabilities unless intentionally exposed through the application boundary.

---

# Capability Contract

Every capability must define:

* unique identifier
* version
* display name
* description
* owner
* input schema
* output schema
* permission requirements
* execution environment
* read/write classification
* approval requirement
* timeout
* retry policy
* idempotency behavior
* provenance requirements
* supported interfaces
* expected errors

Capabilities without complete contracts shall not be registered.

---

# Read and Write Classification

Every capability belongs to exactly one category.

Read.

Write.

Read capabilities:

never modify external state.

Write capabilities:

may modify external state only through the Approval Engine.

Mixed capabilities are prohibited.

---

# Capability Discovery

Capabilities shall be discovered through registration.

Never through:

keyword lists

prompt instructions

manual routing tables

string matching

hardcoded conditionals

The registry is the single source of truth.

---

# Capability Execution

Capability execution always follows the same process.

```text
Capability Requested

↓

Registry Lookup

↓

Input Validation

↓

Permission Check

↓

Approval Check

↓

Execution

↓

Output Validation

↓

Provenance Recording

↓

Audit Recording
```

Execution paths must remain deterministic.

---

# Request Execution Pipeline

Every request entering Echo follows the same architectural pipeline.

No interface may introduce an alternative execution path.

```text
User Request

↓

Intent Builder

↓

Context Builder

↓

Capability Planner

↓

Approval Checker

↓

Capability Executor

↓

Execution Verifier

↓

Evidence Collector

↓

Response Generator

↓

Persistence

↓

Audit
```

This pipeline governs:

chat

dashboard

voice

mobile

future APIs

future automation

Every interface ultimately executes the same application workflow.

---

# Intent Builder

The Intent Builder determines:

what the user is attempting to accomplish.

It does not determine:

how the request will execute.

Intent is descriptive.

Not executable.

---

# Context Builder

The Context Builder assembles all information required for execution.

Possible context sources include:

conversation

memory

projects

calendar

portfolio

research

user preferences

recent activity

retrieved documents

Context assembly remains deterministic whenever possible.

---

# Capability Planner

The Capability Planner determines:

which registered capabilities are required.

It may choose:

one capability

multiple capabilities

no capability

It may never invent a capability.

Language models MAY propose execution plans using registered capabilities.

Deterministic application logic SHALL validate capability availability, permissions, approval requirements, and execution eligibility.

Language models SHALL NOT register capabilities, authorize capabilities, or execute capabilities directly.

---

# Approval Checker

The Approval Checker evaluates:

permission requirements

approval requirements

proposal validity

proposal expiration

approval binding

execution authorization

Approval decisions are deterministic.

Models do not determine approval.

---

# Capability Executor

The Capability Executor invokes registered capabilities.

Execution always occurs through capability contracts.

Execution never bypasses:

validation

permissions

approval

audit

provenance

---

# Evidence Collector

Evidence is collected before response generation.

Evidence includes:

provider results

calculations

citations

provenance

verification status

confidence

missing information

The response generator consumes evidence.

It does not generate evidence.

---

# Response Generator

The Response Generator produces the user facing response.

Responsibilities include:

synthesis

explanation

clarification

reasoning

recommendations

The Response Generator shall never invent missing evidence.

---

# Persistence

After execution the platform persists appropriate records.

Examples:

conversation

messages

tool calls

model calls

memory updates

approval records

audit events

Only durable information should be persisted.

---

# Audit

Every significant request concludes with audit recording.

Audit is mandatory.

Audit shall include:

correlation identifier

timestamp

capabilities used

provider interactions

approval references

execution result

verification status

Audit must remain immutable.

---

# Cross Domain Coordination

Domains shall never directly coordinate other domains.

Application workflows own coordination.

Example:

Allowed:

```text
Application Workflow

↓

Portfolio Domain

↓

Research Domain

↓

Calendar Domain
```

Forbidden:

```text
Portfolio Domain

↓

Calendar Domain
```

or

```text
Research Domain

↓

Email Domain
```

Hidden coupling is prohibited.

---

# Domain Events

Echo adopts an event driven architecture within the modular monolith.

Domains publish events.

Domains do not invoke each other directly.

Application workflows may subscribe to domain events.

Future distributed execution should require minimal architectural change.

---

# Event Principles

Events represent completed business facts.

Not intentions.

Not commands.

Events should be immutable.

Events should remain versioned.

Events should contain sufficient context for downstream consumers.

---

# Example Events

Examples include:

PortfolioSnapshotCreated

PortfolioReconciled

ResearchCompleted

ResearchEvidenceUpdated

CalendarSynced

CalendarProposalCreated

CalendarProposalApproved

EmailIndexed

EmailClassified

MemoryCandidateCreated

MemoryPromoted

MemorySuperseded

ApprovalCreated

ApprovalGranted

ApprovalRejected

ApprovalExpired

ActionExecuted

ExecutionVerified

ExecutionFailed

NotificationCreated

ProjectUpdated

ConversationCompleted

These events establish communication boundaries.

They are not API endpoints.

---

# Event Ownership

The originating domain owns the event definition.

Consumers may subscribe.

Consumers may not redefine the event.

Events shall remain stable contracts.

Breaking changes require versioning.

---

# Event Delivery

The initial implementation MAY use synchronous in-process publication.

Event contracts SHALL remain transport-independent so asynchronous or distributed delivery may be introduced later through an ADR when operational requirements justify it.

Future event infrastructure SHALL NOT be scaffolded before it is required.

Events should not assume a specific transport implementation.

Redis.

PostgreSQL.

Kafka.

Any future event transport remains replaceable.

---

# Domain Isolation

A domain SHOULD minimize dependencies on other domains and communicate through application workflows or domain events whenever possible.

Dependencies should remain minimal.

Communication should occur through:

application workflows

events

interfaces

Never through hidden imports.

---

# Bounded Context Principle

Each domain represents one bounded context.

Concepts should not exist simultaneously inside multiple domains.

Ownership ambiguity is architectural debt.

The Domain Ownership Matrix is the authoritative definition of ownership.

---

---

# Domain Ownership

Every responsibility within Echo has exactly one owner.

No responsibility may have multiple authoritative owners.

Shared ownership is prohibited.

If ownership becomes ambiguous, the architecture must change.

The authoritative ownership mapping is maintained in `DOMAIN_OWNERSHIP.md`.

This document is constitutionally binding.

---

# Single Source of Truth

Every important concept shall have exactly one authoritative location.

Examples:

Portfolio positions have one source of truth.

Calendar events have one source of truth.

User memories have one source of truth.

Approval proposals have one source of truth.

Provider credentials have one source of truth.

Configuration has one source of truth.

Duplication of authoritative state is prohibited.

---

# State Ownership

State belongs to the domain that owns the business concept.

Application workflows may coordinate state.

They do not own it.

Providers may retrieve state.

They do not own it.

Infrastructure stores state.

It does not own it.

---

# Immutable Records

Historical records should be immutable whenever practical.

Examples:

Portfolio snapshots

Research evidence

Audit events

Execution history

Conversation history

Approval history

Rather than modifying historical records, new records should supersede older ones.

Historical accuracy is preferred over mutation.

---

# Memory Philosophy

Memory is a product feature.

Memory is not conversation history.

Memory represents durable knowledge.

Conversation represents interaction history.

These concepts shall remain separate.

---

# Memory Principles

Durable memory must satisfy all of the following:

relevant

useful

persistent

reviewable

traceable

Memories should not exist merely because information appeared once.

---

# Memory Lifecycle

Memory follows a controlled lifecycle.

```text
Observation

↓

Candidate

↓

Review

↓

Promotion

↓

Usage

↓

Supersession

↓

Archive
```

Promotion into durable memory should remain conservative.

False memories are more damaging than forgotten information.

---

# Memory Confidence

Memory records SHOULD include confidence whenever confidence meaningfully affects downstream reasoning or retrieval.

Confidence shall never be binary.

Confidence should increase through repeated verification.

Confidence should decrease when contradictory evidence appears.

---

# Conversation History

Conversation history is immutable.

Conversation history should not be rewritten.

Corrections produce new records.

Not modifications.

---

# Audit Philosophy

Audit exists to answer:

What happened?

Why?

Who initiated it?

Which capability executed?

Which evidence existed?

Which approval authorized it?

Which provider responded?

Which model reasoned?

Every consequential action must be reconstructable.

---

# Observability

Echo should expose observable behavior.

Every important workflow should provide:

logging

metrics

timing

errors

correlation identifiers

tracing

Observability is designed into architecture.

Not added afterward.

---

# Correlation IDs

Every request shall receive a correlation identifier.

That identifier should remain attached to:

logs

provider calls

events

capability execution

approval records

responses

audit entries

Correlation IDs make complete execution reconstruction possible.

---

# Logging Philosophy

Logs exist for engineers.

Responses exist for users.

These responsibilities remain separate.

Logs should contain:

execution flow

timing

failures

warnings

provider activity

retry activity

Logs should never become business logic.

---

# Error Philosophy

Errors are expected.

Architecture should contain failures.

Failures should remain localized.

Unexpected failures should degrade gracefully whenever possible.

---

# Error Classification

Errors should be categorized.

Examples:

ValidationError

PermissionError

ProviderUnavailable

TimeoutError

AuthenticationError

RateLimitError

ConfigurationError

ExecutionError

UnexpectedError

Errors should remain meaningful.

Generic exceptions should be minimized.

---

# Failure Isolation

Provider failures should not corrupt domain state.

Partial failures should remain isolated.

The failure of one capability should not compromise unrelated capabilities.

---

# Retry Philosophy

Retries belong to providers.

Not domains.

Retry policies should be deterministic.

Retries should never duplicate write operations unless idempotency guarantees exist.

---

# Idempotency

Write execution should be idempotent whenever possible.

Repeated approval execution should never produce duplicated external actions.

Idempotency keys should be preserved throughout execution.

---

# Configuration Philosophy

Configuration is data.

Not code.

Configuration should remain centralized.

Configuration values should never be scattered throughout implementation.

---

# Secrets

Secrets shall never appear inside:

source code

tests

documentation

sample configuration

logs

Secrets belong inside secure secret management.

---

# Time

The platform owns time.

System time should never be read directly throughout the codebase.

A centralized clock abstraction SHOULD be used wherever deterministic testing or scheduling benefits from time abstraction.

This improves:

testing

simulation

determinism

future scheduling

---

# Identity

Every significant entity should possess a stable identifier.

Identifiers should remain immutable.

Human readable names are not identifiers.

---

# Versioning

Externally consumed contracts SHOULD be versioned unless they are strictly internal implementation details.

Examples:

capabilities

events

provider contracts

API contracts

Breaking changes require version changes.

---

# Backward Compatibility

Backward compatibility should be preserved whenever practical.

Breaking changes require:

documentation

migration strategy

version increment

ADR approval

---

# Security Philosophy

Security is architectural.

Not procedural.

Every feature should begin with least privilege.

Security should not depend upon developer memory.

---

# Least Privilege

Echo shall request only the permissions necessary for current functionality.

Future permissions should not be requested preemptively.

Every permission must have an explicit architectural justification.

---

# Authentication

Authentication establishes identity.

Authorization establishes permission.

These responsibilities remain separate.

---

# Authorization

Authorization should remain deterministic.

Language models shall never determine permissions.

Permission evaluation belongs to deterministic code.

---

# Privacy

User information belongs to the user.

Echo should minimize:

collection

retention

duplication

exposure

Sensitive information should remain compartmentalized.

---

# Performance Philosophy

Performance matters.

Correctness matters more.

Optimization shall never reduce architectural clarity without measurable justification.

Premature optimization is prohibited.

---

# Scalability

Scalability follows demonstrated need.

Echo should not introduce distributed architecture solely because future growth is possible.

The modular monolith is the default architecture.

Extraction requires evidence.

---

# Testing Philosophy

Testing is a first class engineering activity.

Every phase should leave the repository in a verifiably working state.

Testing is continuous.

Not a final phase.

---

# Testing Pyramid

Echo should maintain balanced testing.

Unit tests.

Integration tests.

Contract tests.

End-to-end tests.

Regression tests.

No layer should rely exclusively on end-to-end testing.

---

# Architecture Regression Tests

Architecture itself shall be tested.

Automated tests should enforce:

dependency direction

forbidden imports

layer isolation

provider isolation

domain isolation

repository structure

Examples include:

API never imports providers.

Domains never import domains.

Providers never expose vendor SDK models.

Application owns orchestration.

Repository ownership remains intact.

Architectural drift should fail CI before human review.

---

# Documentation Philosophy

Documentation is part of the product.

Architecture documentation must evolve alongside implementation.

Undocumented architecture changes are considered incomplete work.

---

# Documentation Requirements

Every major architectural component should document:

purpose

ownership

dependencies

public contracts

responsibilities

non-responsibilities

Documentation should explain *why* more often than *how*.

---

# Code Review Philosophy

Code review evaluates:

correctness

architecture

maintainability

clarity

ownership

testability

Not merely formatting.

---

# Engineering Discipline

Engineers should optimize for future readability.

The next engineer should understand:

why something exists

why alternatives were rejected

where ownership resides

how changes propagate

Architecture is communication.

---

# Maintainability

Echo is expected to exist for many years.

Architecture decisions should optimize for long-term maintainability rather than short-term implementation speed.

Every implementation should leave the repository easier to understand than before.

Technical debt should be treated as an explicit decision, not an accidental byproduct.

---

# Technical Debt

Technical debt is acceptable only when:

* explicitly documented
* intentionally accepted
* time bounded
* assigned an owner
* tracked for future resolution

Undocumented technical debt is considered an architectural defect.

---

# Refactoring

Refactoring is encouraged when it improves:

* clarity
* ownership
* simplicity
* testability
* maintainability

Refactoring should not change externally observable behavior unless explicitly intended.

Large refactors should be supported by automated tests.

---

# Architectural Integrity

Architecture shall remain internally consistent.

No feature may introduce exceptions to architectural rules merely for convenience.

When a new requirement conflicts with the Constitution, the architecture must evolve through the ADR process rather than accumulating special cases.

Consistency is more valuable than cleverness.

---

# Feature Philosophy

Features are additions to the platform.

Architecture is the platform itself.

Architecture should remain stable while features continue to evolve.

The repository should grow through new capabilities rather than increasing architectural complexity.

---

# Incremental Development

Large implementations should be decomposed into independently verifiable increments.

Every increment should:

* compile
* pass tests
* update documentation
* leave the repository deployable

No implementation phase should knowingly leave the project in a broken state.

---

# Explicitness

Echo favors explicit behavior over implicit behavior.

Examples:

Prefer:

* explicit ownership
* explicit dependencies
* explicit contracts
* explicit configuration
* explicit capability registration

Avoid:

* hidden behavior
* implicit imports
* magic strings
* convention-only execution
* undocumented assumptions

---

# Naming

Names should communicate responsibility.

A name should describe:

* what something owns
* what it does
* what it does not do

Avoid ambiguous names.

Examples of discouraged names:

* Manager
* Helper
* Utility
* Common
* Stuff
* Misc
* Processor
* Engine

unless their responsibility is narrowly and precisely defined.

---

# Business Language

Business terminology should remain consistent across:

* code
* documentation
* database schema
* APIs
* events
* capabilities

A concept should not have multiple names.

Likewise, different concepts should not share the same name.

---

# Stable Interfaces

Public interfaces should change slowly.

Internal implementation may evolve freely.

Consumers should depend on contracts rather than implementation details.

---

# Extensibility

Echo should be easy to extend without modifying unrelated components.

New capabilities should primarily require:

* new domain logic
* new capability registration
* new provider implementation (if necessary)

Existing architecture should rarely require modification.

---

# Composition Over Inheritance

Echo favors composition.

Inheritance should be reserved for cases where a genuine "is-a" relationship exists.

Behavior should be composed from smaller components whenever practical.

---

# Dependency Injection

Dependencies should be explicit.

Construction should occur at application boundaries.

Hidden global state should be avoided.

Dependency injection exists to improve:

* testing
* replaceability
* clarity

---

# Global State

Mutable global state is prohibited.

Shared mutable state increases coupling and reduces predictability.

State should remain owned by explicit components.

---

# Concurrency

Concurrency should be introduced only where measurable benefit exists.

Correctness must remain deterministic regardless of execution model.

Parallel execution must not violate domain invariants.

---

# Background Work

Long-running work should execute outside request lifecycles whenever practical.

Background execution should remain observable.

Background work must produce:

* logs
* events
* audit records
* correlation identifiers

---

# Scheduling

Scheduled execution is a capability.

Scheduling is not a special execution path.

Scheduled work must follow the same architectural rules as user-initiated work.

---

# Caching

Caching is an optimization.

Caching is never a source of truth.

The system should function correctly with caching disabled.

Cache invalidation should be deterministic whenever possible.

---

# Persistence

Persistent storage exists to preserve authoritative state.

Transient execution state should remain outside persistent storage whenever practical.

Persistence should remain implementation independent.

---

# Database Philosophy

Databases store data.

Domains define meaning.

Business rules do not belong in database implementations.

---

# Migrations

Database schema evolution should occur through explicit migrations.

Schema changes should be:

* reversible when practical
* documented
* version controlled
* reviewed

---

# Provider Evolution

External providers will change.

Echo should isolate provider evolution behind provider adapters.

A provider replacement should affect:

provider implementation

configuration

registration

It should not require domain redesign.

---

# Artificial Intelligence

Language models are reasoning tools.

They are not system architects.

They are not sources of truth.

They are not business rule engines.

They are not permission systems.

They are not financial calculators.

They are not execution engines.

Their role is reasoning over verified information.

All model output is untrusted input.

Structured model output SHALL be schema validated before use.

Model-generated factual claims, classifications, mappings, and calculations SHALL be verified according to the risk of the operation before becoming authoritative system state.

---

# Prompt Philosophy

Prompts are implementation details.

Business behavior must never depend solely upon prompt wording.

If changing a prompt changes deterministic business behavior, the architecture is incorrect.

---

# Prompt Storage

Prompts should be:

versioned

reviewable

testable

replaceable

Prompt evolution should be documented.

---

# Model Routing

Model selection is an architectural concern.

Model routing should optimize for:

* correctness
* latency
* cost
* capability requirements
* safety

Routing decisions should remain deterministic whenever practical.

---

# Vendor Neutrality

Echo belongs to the user.

Not to any model vendor.

Not to any cloud provider.

Not to any API provider.

Vendor lock-in is considered architectural debt.

---

# Repository as Documentation

A competent engineer should understand Echo by reading:

directory structure

file names

documentation

interfaces

tests

The repository should explain itself.

---

# Architectural Reviews

Major architectural reviews should occur periodically.

Reviews should evaluate:

* ownership
* coupling
* complexity
* maintainability
* documentation
* technical debt
* architectural drift

Architecture should evolve intentionally.

---

# Constitutional Violations

Constitutional violations should be treated as engineering defects.

Examples include:

* hidden ownership
* duplicated business rules
* provider leakage
* circular dependencies
* undocumented architecture
* speculative abstractions
* domain coupling
* bypassing approvals
* bypassing capability registration
* bypassing audit
* bypassing provenance
* business logic inside presentation layers

These violations should be corrected before introducing additional functionality whenever practical.

---

# Constitutional Amendment Process

This Constitution is intentionally stable.

Amendments require:

1. Identification of the architectural deficiency.
2. Written justification.
3. Architecture Decision Record.
4. Review of downstream impact.
5. Approval.
6. Documentation updates.
7. Implementation updates.
8. Regression verification.

The Constitution shall not evolve through undocumented implementation.

---

# Final Principle

Every engineer working on Echo should strive to leave the system:

simpler,

clearer,

safer,

more deterministic,

better documented,

and easier to extend

than it was before they began.

Architecture is not measured by the number of components it contains.

Architecture is measured by how easily future engineers can understand, trust, and extend the system.

Echo should remain a system whose structure explains itself.

---


# Architectural Anti-Patterns

The following architectural patterns are explicitly prohibited within Echo.

These are considered constitutional violations rather than stylistic preferences.

---

## Business Logic Inside API Routes

API routes exist solely to:

* authenticate requests
* validate input
* invoke application workflows
* serialize responses

Business logic shall never reside inside API routes.

---

## Business Logic Inside Providers

Providers translate external systems.

Providers do not own business behavior.

Business rules belong to domains.

---

## Provider SDK Leakage

Provider SDK objects shall never escape provider boundaries.

Every external object must be normalized into Echo contracts before reaching the Domain layer.

Example (Forbidden):

```text
Portfolio Domain

↓

SchwabPosition
```

Example (Required):

```text
Portfolio Domain

↓

NormalizedPosition
```

---

## Domain-to-Domain Imports

Domains shall never import one another directly.

Cross-domain collaboration belongs exclusively to the Application layer.

---

## Circular Dependencies

Circular imports are prohibited.

Circular ownership is prohibited.

Circular execution paths are prohibited.

If circular dependencies appear, ownership has become incorrect.

---

## Hidden Execution Paths

Every executable action must pass through:

Capability Registry

↓

Validation

↓

Permission Check

↓

Approval (when required)

↓

Execution

↓

Verification

↓

Audit

No hidden shortcuts may exist.

---

## Hidden State Mutation

State changes should always be observable.

Silent mutation is prohibited.

State transitions should generate:

* events
* audit records
* provenance
* history (when appropriate)

---

## Duplicate Business Rules

A business rule should exist in exactly one place.

Examples of prohibited duplication:

Portfolio allocation rules implemented twice.

Approval rules copied across domains.

Risk thresholds duplicated inside prompts.

Permission logic duplicated across APIs.

Duplication creates inconsistent behavior.

---

## Prompt-Defined Business Logic

Prompts may influence reasoning.

Prompts may not define deterministic platform behavior.

Examples of prohibited prompt behavior:

"Calculate allocation percentages."

"Determine whether approval is required."

"Decide whether the portfolio exceeds concentration limits."

These belong to deterministic code.

---

## Prompt-Based Capability Routing

Capability selection shall not depend upon prompt wording.

Capabilities are selected from the Capability Registry.

Routing should remain deterministic.

---

## Hidden Configuration

Configuration shall never exist as scattered constants throughout the repository.

Configuration should remain centralized, documented, and version controlled.

---

## Magic Strings

Behavior should not depend upon undocumented string literals.

Named constants or strongly typed representations are preferred.

---

## Global Mutable State

Global mutable state introduces hidden coupling.

State should remain explicitly owned.

---

## Speculative Architecture

Echo shall not implement abstractions solely because they may become useful later.

Examples:

Unused interfaces.

Unused providers.

Unused repositories.

Unused event systems.

Unused domain packages.

Unused database models.

Architecture grows through demonstrated need.

---

## Premature Distribution

Microservices are not a feature.

Distributed systems shall not be introduced without measurable operational justification.

The modular monolith remains the constitutional default.

---

## Repository Layers by Technology

Repository organization should reflect business concepts.

Avoid repositories organized primarily by technology.

Discouraged:

```text
controllers/

services/

models/

utils/

helpers/
```

Preferred:

```text
portfolio/

calendar/

research/

memory/

approvals/
```

---

## Generic Utility Modules

Large utility collections indicate missing ownership.

Generic modules such as:

```text
utils/

common/

shared/

misc/
```

require an approved ADR.

---

## Monolithic Domain Services

A single service responsible for every behavior inside a domain is discouraged.

Responsibilities should remain cohesive.

Growing services should be decomposed into meaningful collaborators.

---

## Large Conditional Routing

Large switch statements based on capability names, provider names, or intent names should be avoided.

Registration should replace branching.

---

## Hidden Coupling

Components should not rely upon undocumented assumptions about one another.

Dependencies should remain explicit.

---

## Runtime Discovery of Ownership

Ownership should never require runtime inspection.

A reader should determine ownership directly from the repository structure.

---

## Anonymous Events

Events should have stable names.

Events should represent business facts.

Generic events such as:

EventOccurred

ActionFinished

SomethingChanged

should be avoided.

---

## Ambiguous Naming

Names should communicate ownership.

Avoid:

Manager

Processor

Engine

Thing

Helper

Utility

Handler

unless the responsibility is narrowly defined.

---

## Business Logic Inside Templates

Presentation templates should never contain business rules.

Presentation formats data.

Domains determine meaning.

---

## Business Logic Inside Frontend

The frontend is an interface.

It is not an authoritative execution environment.

Business rules belong to the backend.

---

## Bypassing the Approval Engine

No write operation may bypass the Approval Engine.

Direct execution is prohibited.

---

## Bypassing Provenance

Externally derived information without provenance should never become authoritative.

Every important fact should identify its origin.

---

## Bypassing Audit

Consequential actions without audit records are prohibited.

Audit is mandatory.

---

## Bypassing Capability Registration

Executable behavior must be registered.

Hidden execution paths are constitutional violations.

---

## Provider-Specific Domains

Domains should remain vendor neutral.

Examples of prohibited domains:

GoogleCalendarDomain

SchwabPortfolioDomain

ClaudeReasoningDomain

Domains own business concepts.

Providers own vendor implementations.

---

## Leaking Infrastructure

Infrastructure implementation details should remain below the domain layer.

Examples:

Database sessions.

Redis clients.

HTTP clients.

SDK objects.

These should never appear inside domain behavior.

---

## Multiple Sources of Truth

Every important concept has one authoritative owner.

Conflicting authoritative records are prohibited.

---

## Excessive File Growth

Large files usually indicate misplaced responsibilities.

Large files should trigger architectural review before becoming permanent.

---

## Excessive Function Growth

Large functions usually indicate missing abstraction.

Complexity should be decomposed.

---

## Documentation Drift

Documentation should evolve alongside implementation.

Architecture documentation that no longer reflects reality should be treated as a defect.

---

# Provider Due Diligence

Claims regarding provider pricing, limits, capabilities, availability, coverage, or supported features SHALL be verified before becoming architectural assumptions.

Marketing material shall not be treated as authoritative technical documentation.

---

# Constitutional Compliance

Every pull request should be evaluated against this Constitution.

Reviewers should ask:

* Does ownership remain clear?
* Are dependencies still directional?
* Has any domain acquired responsibilities belonging elsewhere?
* Does this introduce duplication?
* Does this introduce provider coupling?
* Does this bypass capability registration?
* Does this bypass approval?
* Does this bypass audit?
* Does this bypass provenance?
* Is an ADR required?

If any answer indicates constitutional drift, the change should be revised before approval.

---

# Closing Statement

The purpose of this Constitution is not to maximize architectural sophistication.

Its purpose is to maximize clarity.

A future engineer should be able to open the Echo repository years from now and understand:

* what each component owns,
* why it exists,
* how requests move through the system,
* where decisions are made,
* how data flows,
* how behavior is verified,
* and how new capabilities should be added.

The greatest compliment this architecture can receive is not that it is clever.

It is that it feels obvious.

That every major decision appears inevitable once the structure is understood.

Echo should remain a system that is easy to reason about, difficult to misuse, and straightforward to extend.

This Constitution exists to preserve that standard.

---

# Related Documents

This Constitution is complemented by the following architecture documents:

* `DOMAIN_OWNERSHIP.md`
* `REQUEST_LIFECYCLE.md`
* `CAPABILITY_REGISTRY.md`
* `DOMAIN_EVENTS.md`
* `MODEL_ROUTING.md`
* `README.md`
* Architecture Decision Records (`/docs/adr/`)
* `SYSTEM_PRINCIPLES.md`
* `PRODUCT_PRINCIPLES.md`

Each document expands upon a specific constitutional area without superseding this Constitution.

---

# Change History

| Version | Date | Description |
|----------|------|-------------|
| 1.0 | July 2026 | Initial constitutional architecture freeze for Echo V3. Establishes engineering philosophy, architectural governance, layering, capability-first execution, ownership rules, approval architecture, provider abstraction, testing standards, documentation standards, and long-term repository governance. |

---

**END OF CONSTITUTION.md**

**Version 1.0 — Architecture Freeze**