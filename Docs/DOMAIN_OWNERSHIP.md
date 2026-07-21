Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Domain Ownership

## Purpose

This document defines authoritative ownership boundaries for every business concept within the Echo Personal AI Operating System.

Its purpose is to eliminate ambiguity regarding:

• business responsibility
• state ownership
• business rule ownership
• persistence ownership
• provider ownership
• event ownership
• public interfaces
• cross-domain communication

Every business concept shall have exactly one authoritative owner.

Ownership ambiguity is considered architectural debt.

This document expands upon the ownership principles established in CONSTITUTION.md.

If implementation disagrees with this document, this document takes precedence unless superseded by an approved Architecture Decision Record (ADR).

---

# Constitutional Relationship

This document derives its authority from CONSTITUTION.md.

It does not redefine constitutional principles.

Instead, it assigns concrete ownership for the business concepts governed by those principles.

The Constitution defines architectural law.

This document defines architectural ownership.

---

# Scope

This document governs ownership of:

• domains
• business concepts
• business rules
• authoritative state
• repositories
• public interfaces
• domain events
• provider relationships
• cross-domain interactions

This document does not define:

• implementation details
• request execution
• capability contracts
• provider implementations
• API routing
• infrastructure configuration

Those responsibilities belong to their respective architecture documents.

---

# Ownership Philosophy

Echo is organized around business ownership.

Not technology.

Not frameworks.

Not providers.

Not databases.

A domain exists because it owns a business capability.

Every architectural decision should begin with the question:

"Which business capability owns this concept?"

The answer determines ownership.

---

# Core Ownership Principles

## Single Owner Principle

Every business concept shall have exactly one authoritative owner.

Ownership shall never be shared.

If multiple domains appear to own the same concept, the architecture is incorrect.

---

## State Ownership Principle

Every durable business record has one owning domain.

Only the owning domain may:

• create
• modify
• validate
• delete
• define invariants

Other domains may consume state.

They do not own it.

---

## Business Rule Principle

Business rules belong exclusively to the domain owning the business concept.

Examples:

Portfolio owns allocation rules.

Calendar owns scheduling rules.

Email owns message classification rules.

Memory owns promotion rules.

Approvals owns approval lifecycle rules.

No other domain may duplicate those rules.

---

## Persistence Principle

Persistence follows business ownership.

Repositories belong to the domain that owns the underlying business concept.

Persistence technology does not determine ownership.

Business ownership determines persistence ownership.

---

## Event Principle

A domain owns every event describing its business facts.

Consumers may subscribe.

Consumers may not redefine ownership.

Events never transfer ownership.

---

## Interface Principle

Public interfaces expose domain capabilities.

Interfaces do not transfer ownership.

The owning domain remains authoritative regardless of how many consumers exist.

---

## Provider Principle

Providers never own business concepts.

Providers translate external systems into Echo contracts.

Business ownership always remains inside domains.

Examples:

Google Calendar does not own calendar events.

Schwab does not own portfolio positions.

Gmail does not own email state.

Claude does not own reasoning outcomes.

Providers implement integration.

Domains own meaning.

---

## Application Principle

The Application layer coordinates domains.

It never owns business state.

It never owns business rules.

Coordination is not ownership.

---

# Ownership Decision Framework

Whenever ownership is uncertain, the following decision process shall be applied.

Question 1

Which business capability exists even if every provider disappeared?

That capability is the ownership candidate.

↓

Question 2

Which domain defines the business rules?

If only one domain answers this question, that domain owns the concept.

↓

Question 3

Which domain defines the lifecycle?

Creation.

Modification.

Validation.

Supersession.

Deletion.

That domain owns the concept.

↓

Question 4

Which domain would still exist if every consumer disappeared?

Consumers do not own concepts.

Owners do.

↓

Question 5

If two domains still appear to own the concept...

The architecture is incorrect.

Ownership shall be restructured rather than shared.

---

# Domain Catalog

Echo Version 1.0 consists of the following bounded business domains.

• Portfolio
• Research
• Calendar
• Email
• Memory
• Conversation
• Projects
• Identity
• Notifications
• Approvals
• Capabilities
• Knowledge
• System

These are the only authoritative business domains within the platform.

Additional domains require an approved Architecture Decision Record.

---

# Domain Dependency Graph

Business domains own business capabilities.

The Application layer coordinates interactions between domains.

Providers implement integrations without owning business concepts.

Ownership does not flow between domains.

Business Domains
        │
        ▼
+--------------------------------------------------------------+
| Portfolio | Research | Calendar | Email | Memory | Projects |
| Conversation | Identity | Notifications | Approvals         |
| Capabilities | Knowledge | System                        |
+--------------------------------------------------------------+
        ▲
        │
Application (coordination only)
        │
        ▼
Providers / Infrastructure

---

# Domain Responsibilities

Every domain owns five categories of responsibility.

Business Concepts

Business Rules

Authoritative State

Published Events

Public Interfaces

Every domain definition in this document shall explicitly identify each category.

---

# Ownership Matrix Principles

The ownership matrices contained within this document are normative.

They define:

• authoritative ownership
• permitted dependencies
• permitted consumers
• provider relationships
• write authority
• read authority

Matrices are authoritative.

Narrative descriptions must remain consistent with the matrices.

If a discrepancy exists, the matrices take precedence.

---

# Interpretation Rules

Throughout this document:

Owns

means authoritative ownership.

Consumes

means read access without ownership.

Coordinates

means orchestration through the Application layer.

Publishes

means originating domain events.

Subscribes

means consuming events produced by another domain.

Implements

means infrastructure or provider implementation without business ownership.

These terms shall be interpreted consistently throughout this document.

---

# Financial & Core Productivity Domains

This section defines the ownership boundaries for Echo's primary business
domains.

These domains represent the highest-value capabilities of the platform and
own the majority of user-facing business concepts.

---

# Portfolio Domain

## Purpose

The Portfolio domain owns the user's investment portfolio and all business
concepts required to understand, evaluate, monitor, and manage it.

Portfolio is the authoritative source of truth for investment state.

No other domain may authoritatively represent portfolio state.

---

## Owns

Investment Accounts

Brokerage Accounts

Retirement Accounts

Portfolio Positions

Holdings

Cash Positions

Lots

Cost Basis

Transactions

Transfers

Corporate Actions

Portfolio Snapshots

Allocation

Asset Allocation

Sector Allocation

Geographic Allocation

Account Allocation

Portfolio Performance

Performance History

Portfolio Benchmarks

Watchlists

Investment Policy Statement (IPS)

IPS Compliance Evaluation

Concentration Analysis

Diversification Analysis

Exposure Analysis

Rebalancing Proposals

Portfolio Health Metrics

Portfolio Import History

Portfolio Reconciliation Results

Portfolio Configuration

---

## Does NOT Own

Company fundamentals

Macroeconomic analysis

Research reports

News

Calendar events

Tasks

Projects

Emails

Durable memory

Conversation history

Approval lifecycle

Notifications

Provider credentials

Identity

---

## Business Rules

Portfolio owns rules governing:

position construction

portfolio composition

allocation calculations

performance calculations

benchmark comparison

concentration limits

portfolio health

IPS evaluation

rebalancing logic

portfolio reconciliation

account aggregation

portfolio state consistency

No other domain may duplicate these rules.

---

## Authoritative State

Portfolio is the single source of truth for:

accounts

positions

holdings

cash

cost basis

transactions

snapshots

watchlists

portfolio metrics

IPS documents

IPS evaluation results

rebalancing proposals

portfolio configuration

---

## Public Interfaces

Portfolio exposes read capabilities for:

portfolio summary

accounts

positions

holdings

allocation

performance

watchlists

portfolio health

IPS status

rebalancing recommendations

Portfolio exposes write capabilities for:

portfolio synchronization

watchlist management

portfolio configuration

IPS management

approved portfolio actions

All write operations follow the Approval Engine.

Portfolio-owned Rebalancing Proposals are portfolio recommendations.

Before any external portfolio modification may occur, a Rebalancing Proposal SHALL be submitted to the Approvals domain as an Approval Proposal.

Execution may proceed only after the corresponding Approval Proposal has been approved.

---

## Published Events

PortfolioImported

PortfolioSynchronized

PortfolioSnapshotCreated

PortfolioSnapshotArchived

PortfolioReconciled

PositionCreated

PositionClosed

HoldingUpdated

WatchlistUpdated

IPSUpdated

IPSComplianceEvaluated

PortfolioHealthUpdated

RebalancingProposalCreated

---

## Subscribed Events

ApprovalGranted

ApprovalRejected

ProviderSynchronizationCompleted

IdentityUpdated

---

## External Providers

Schwab

Fidelity

Interactive Brokers

JP Morgan

Vanguard

CSV Import

Future custodians

Providers normalize data.

Portfolio owns meaning.

---

## Consumers

Research

Conversation

Dashboard

Notifications

Projects

Application Workflows

Consumers receive Portfolio contracts.

Consumers never mutate Portfolio state.

---

## Repository Ownership

Portfolio repositories own persistence for:

accounts

positions

transactions

holdings

snapshots

watchlists

IPS

portfolio metrics

No other repository may persist these concepts.

---

# Research Domain

## Purpose

Research owns the collection, normalization, synthesis, and evaluation of
investment information.

Research explains the world.

Portfolio explains the user's investments.

---

## Owns

Company Profiles

Security Master

Tickers

Identifiers

Market Data

Fundamental Data

Financial Statements

Analyst Estimates

Consensus Ratings

Economic Indicators

Macroeconomic Data

Industry Data

News

Research Reports

Research Evidence

Evidence Provenance

Investment Theses

Research Notes

Catalysts

Risks

Opportunities

Valuation Models

Scenario Analysis

Research Watchlists

Research Tasks

Source Reliability

Evidence Confidence

Research History

Insider Transaction Data

Congressional Trading Disclosures

Institutional Ownership Data

Ownership Change History

Trading Anomaly Detection

Personal Baseline Trading Profiles

Committee Correlation Analysis

Sector Correlation Analysis

Research Signals

---

## Does NOT Own

Portfolio positions

Accounts

Cost basis

Transactions

Portfolio allocation

IPS

Calendar

Email

Memory

Identity

Approvals

---

## Business Rules

Research owns:

evidence collection

source normalization

evidence confidence

thesis evaluation

valuation methodology

research synthesis

source credibility

citation generation

news relevance

macro interpretation

company analysis

insider transaction normalization

congressional disclosure normalization

ownership trend analysis

personal baseline anomaly detection

committee correlation analysis

sector correlation analysis

research signal generation

Research never owns portfolio decisions.

---

## Authoritative State

Research is authoritative for:

research documents

security master

normalized market data

news

research evidence

investment theses

valuation models

research history

evidence provenance

insider transaction records

congressional trading records

ownership history

anomaly detection results

correlation analyses

generated research signals

---

## Public Interfaces

Research exposes:

company lookup

ticker lookup

security search

research retrieval

news retrieval

valuation summaries

thesis summaries

evidence summaries

macro summaries

citation retrieval

Research write capabilities include:

research ingestion

evidence updates

thesis management

security master updates

provider synchronization

---

## Published Events

ResearchCompleted

ResearchEvidenceUpdated

SecurityMasterUpdated

NewsIngested

ThesisUpdated

CatalystDetected

ResearchConfidenceChanged

MarketDataUpdated

InsiderActivityDetected

CongressionalTradeDetected

TradingAnomalyDetected

OwnershipTrendUpdated

ResearchSignalGenerated

---

## Subscribed Events

PortfolioSnapshotCreated

ProviderSynchronizationCompleted

ScheduledResearchRequested

---

## External Providers

SEC

EDGAR

Polygon

Financial Modeling Prep

Yahoo Finance

Reuters

Bloomberg

Reddit

Company IR

Future market providers

---

## Consumers

Portfolio

Conversation

Dashboard

Projects

Notifications

Memory

Application Workflows

---

## Repository Ownership

Research repositories own:

security master

research documents

research evidence

news

valuation models

macro datasets

research history

theses

citations

---

# Calendar Domain

## Purpose

Calendar owns time-based commitments.

It is the authoritative source of scheduled events and proposed scheduling
changes.

---

## Owns

Calendar Events

Meetings

Appointments

Tasks with execution times

Availability

Busy Status

Time Blocks

Focus Sessions

Reminders

Scheduling Proposals

Recurring Events

Travel Time

Calendar Synchronization

Scheduling Preferences

---

## Does NOT Own

Projects

Portfolio

Emails

Research

Notifications

Memory

Approvals

Identity

---

## Business Rules

Calendar owns:

availability

conflict detection

event scheduling

recurrence

time calculations

reminder timing

calendar synchronization

event validation

travel buffers

---

## Authoritative State

Calendar owns:

events

availability

time blocks

reminders

calendar preferences

recurrence rules

---

## Public Interfaces

Read:

today

week

month

availability

next event

free time

Write:

create event

modify event

delete event

move event

accept invitation

decline invitation

All writes require Approval Engine evaluation when externally modifying user
calendars.

---

## Published Events

CalendarEventCreated

CalendarEventUpdated

CalendarEventDeleted

ReminderScheduled

ReminderTriggered

AvailabilityChanged

CalendarSynced

---

## Subscribed Events

ApprovalGranted

ProjectDeadlineChanged

IdentityUpdated

---

## External Providers

Google Calendar

Microsoft Outlook

Apple Calendar

ICS

Future calendar providers

---

## Consumers

Projects

Notifications

Conversation

Dashboard

Application Workflows

---

## Repository Ownership

Calendar repositories own:

events

availability

preferences

reminders

sync metadata

---

# Email Domain

## Purpose

Email owns electronic message management.

It is responsible for representing, organizing, classifying, and interacting
with email.

---

## Owns

Email Messages

Threads

Folders

Labels

Categories

Message Metadata

Attachments

Drafts

Outgoing Messages

Email Classification

Email Summaries

Inbox State

Read Status

Email Synchronization

---

## Does NOT Own

Projects

Calendar

Portfolio

Research

Memory

Identity

Notifications

Approvals

---

## Business Rules

Email owns:

thread construction

message classification

folder organization

label management

draft lifecycle

attachment management

message synchronization

email summarization

---

## Authoritative State

Email owns:

messages

threads

drafts

labels

folders

classification

attachment metadata

email summaries

---

## Public Interfaces

Read:

search

thread

message

attachment metadata

summary

Write:

draft

send

archive

delete

move

label

mark read

mark unread

All external writes require Approval Engine evaluation where applicable.

---

## Published Events

EmailIndexed

EmailReceived

EmailSent

DraftCreated

DraftUpdated

EmailClassified

InboxChanged

---

## Subscribed Events

ApprovalGranted

IdentityUpdated

ProviderSynchronizationCompleted

---

## External Providers

Gmail

Microsoft 365

IMAP

Exchange

Future email providers

---

## Consumers

Projects

Memory

Conversation

Notifications

Dashboard

Application Workflows

---

## Repository Ownership

Email repositories own:

messages

threads

drafts

labels

folders

classification

attachment metadata

sync metadata

---

# User & Personal Knowledge Domains

The domains in this section own the user's identity, knowledge, ongoing work,
and conversational experience.

These domains transform Echo from a collection of tools into a persistent
personal operating system.

---

# Memory Domain

## Purpose

The Memory domain owns durable knowledge about the user and the long-term
information Echo retains across conversations.

Memory exists to improve future decision making and personalization.

Memory is not conversation history.

Memory is not a cache.

Memory is durable knowledge.

---

## Owns

Durable Memories

Memory Entries

Memory Metadata

Memory Confidence

Memory Sources

Memory Promotion

Memory Consolidation

Memory Retrieval

Memory Relationships

Memory Categories

Memory Expiration Policies

Memory Importance Scores

Memory Corrections

Memory Version History

Memory Audit Records

---

## Does NOT Own

Conversation history

Current request state

Portfolio

Research

Calendar

Projects

Identity

Notifications

Provider configuration

---

## Business Rules

Memory owns:

promotion rules

retention rules

retrieval ranking

memory confidence

memory deduplication

memory consolidation

conflict resolution

expiration

memory correction

memory auditing

No other domain may determine what becomes durable memory.

---

## Authoritative State

Memory is authoritative for:

durable memories

memory metadata

confidence scores

promotion history

memory relationships

memory versions

---

## Public Interfaces

Read:

retrieve memories

search memories

related memories

memory summaries

Write:

promote memory

update memory

correct memory

archive memory

delete memory

Memory writes follow the Approval Engine when required by constitutional policy.

---

## Published Events

MemoryCreated

MemoryUpdated

MemoryArchived

MemoryDeleted

MemoryPromoted

MemoryConfidenceChanged

MemoryConflictDetected

---

## Subscribed Events

ConversationCompleted

ApprovalGranted

IdentityUpdated

ProjectCompleted

---

## External Providers

None

The Memory domain owns its business concepts internally.

Embedding services or vector databases are implementation details rather than
business owners.

---

## Consumers

Conversation

Projects

Research

Notifications

Application Workflows

---

## Repository Ownership

Memory repositories own:

durable memories

metadata

confidence

relationships

audit history

promotion history

---

# Conversation Domain

## Purpose

The Conversation domain owns active user interactions.

It represents what is happening now.

Conversation does not own long-term knowledge.

---

## Owns

Conversation Sessions

Conversation Turns

Conversation Context

Session Metadata

Conversation State

Conversation Summaries

Conversation Artifacts

Active Intent

Conversation Timeline

Conversation References

Temporary Context

---

## Does NOT Own

Durable memories

Portfolio

Research

Projects

Calendar

Identity

Notifications

Approvals

---

## Business Rules

Conversation owns:

session lifecycle

conversation continuity

context assembly

artifact association

conversation summarization

session expiration

temporary context

---

## Authoritative State

Conversation owns:

active sessions

conversation history

temporary context

conversation summaries

active artifacts

---

## Public Interfaces

Read:

conversation

history

session

artifacts

context

Write:

new conversation

append turn

close conversation

generate summary

---

## Published Events

ConversationStarted

ConversationCompleted

ConversationSummarized

ConversationArchived

IntentResolved

---

## Subscribed Events

MemoryUpdated

PortfolioUpdated

ResearchCompleted

ProjectUpdated

NotificationDelivered

---

## External Providers

None

LLMs participate in conversations through the Application layer.

Providers never own conversations.

---

## Consumers

Memory

Projects

Notifications

Dashboard

Application Workflows

---

## Repository Ownership

Conversation repositories own:

sessions

turns

summaries

temporary context

artifacts

---

# Projects Domain

## Purpose

Projects owns persistent initiatives requiring multiple coordinated actions
over time.

Projects organize work.

Projects do not execute work.

---

## Owns

Projects

Project Plans

Goals

Milestones

Deliverables

Project Status

Dependencies

Project Notes

Project Timeline

Project Risks

Project Decisions

Project Resources

Project Progress

Project Archives

---

## Does NOT Own

Calendar events

Emails

Portfolio

Research

Conversation

Memory

Notifications

Identity

---

## Business Rules

Projects owns:

project lifecycle

goal tracking

milestone management

dependency management

progress evaluation

project completion

project archival

---

## Authoritative State

Projects owns:

projects

milestones

status

dependencies

notes

progress

project history

---

## Public Interfaces

Read:

projects

status

timeline

milestones

progress

Write:

create project

update project

archive project

complete milestone

update status

---

## Published Events

ProjectCreated

ProjectUpdated

ProjectCompleted

MilestoneCompleted

ProjectArchived

DeadlineChanged

---

## Subscribed Events

CalendarEventCompleted

ApprovalGranted

ConversationCompleted

MemoryUpdated

---

## External Providers

None

Third-party project management systems are providers rather than owners.

---

## Consumers

Conversation

Notifications

Calendar

Dashboard

Application Workflows

---

## Repository Ownership

Projects repositories own:

projects

milestones

dependencies

status

history

---

# Identity Domain

## Purpose

Identity owns the user's profile, preferences, permissions, and persistent
configuration.

Identity defines who the user is within Echo.

---

## Owns

User Profile

User Preferences

System Preferences

Personalization Settings

Approval Preferences

Notification Preferences

Connected Accounts

Provider Configuration

Authentication Metadata

Authorization Metadata

Feature Flags

User Locale

Units

Time Zone

Accessibility Preferences

---

## Does NOT Own

Portfolio

Research

Projects

Calendar

Email

Memory

Conversation

Notifications

Approvals

---

## Business Rules

Identity owns:

user preference resolution

provider configuration

authentication metadata

authorization metadata

personalization configuration

feature availability

---

## Authoritative State

Identity owns:

profile

preferences

provider configuration

feature configuration

connected accounts

user settings

---

## Public Interfaces

Read:

profile

preferences

configuration

connected providers

Write:

update profile

change preferences

connect provider

disconnect provider

update configuration

---

## Published Events

IdentityUpdated

PreferenceChanged

ProviderConnected

ProviderDisconnected

ConfigurationUpdated

---

## Subscribed Events

ApprovalGranted

---

## External Providers

Google

Microsoft

Apple

Authentication Providers

Future identity providers

Providers authenticate users.

Identity owns user representation.

---

## Consumers

All business domains

Application

---

## Repository Ownership

Identity repositories own:

profile

preferences

configuration

provider connections

authorization metadata

---

# Notifications Domain

## Purpose

Notifications owns user-facing delivery of information requiring attention.

Notifications deliver.

They do not decide business meaning.

---

## Owns

Notifications

Notification Queue

Notification Preferences

Delivery Status

Delivery History

Escalation Policies

Reminder Delivery

Notification Channels

Notification Templates

Notification Scheduling

---

## Does NOT Own

Calendar reminders

Portfolio state

Projects

Research

Memory

Conversation

Identity

Business decisions

---

## Business Rules

Notifications owns:

delivery

channel selection

retry policies

escalation

deduplication

delivery tracking

notification suppression

---

## Authoritative State

Notifications owns:

queued notifications

delivery history

delivery status

templates

notification preferences specific to delivery

---

## Public Interfaces

Read:

notification history

delivery status

pending notifications

Write:

queue notification

cancel notification

acknowledge notification

retry notification

---

## Published Events

NotificationQueued

NotificationDelivered

NotificationFailed

NotificationAcknowledged

NotificationExpired

---

## Subscribed Events

PortfolioHealthUpdated

IPSComplianceEvaluated

CalendarEventCreated

ReminderTriggered

EmailReceived

ProjectCompleted

ResearchCompleted

SystemAlertRaised

---

## External Providers

Push Notification Services

SMS Providers

Email Delivery Providers

Desktop Notification Services

Future messaging providers

Providers deliver notifications.

Notifications owns delivery decisions.

---

## Consumers

Conversation

Dashboard

Application Workflows

---

## Repository Ownership

Notification repositories own:

delivery queue

delivery history

templates

delivery metadata

channel configuration

---

# Platform Governance Domains

The domains in this section own the platform capabilities that support every
other business domain.

These domains govern platform behavior but do not own the business concepts
defined by the financial or user domains.

---

# Approvals Domain

## Purpose

The Approvals domain owns Echo's approval lifecycle.

It is the sole authority responsible for determining whether proposed actions
requiring user authorization may proceed.

Approvals own decisions.

They do not execute actions.

---

## Owns

Approval Requests

Approval Proposals

Approval Decisions

Approval Payload Hashes

Approval Expiration

Approval History

Approval Audit Records

Approval Policies

Approval Sessions

Approval State

Approval Metadata

Approval Reasoning

Approval Invalidation

---

## Does NOT Own

Portfolio state

Calendar events

Emails

Projects

Memory

Conversation

Provider execution

Capability implementations

---

## Business Rules

Approvals owns:

approval lifecycle

approval validation

payload integrity

approval expiration

approval invalidation

approval audit

approval replay prevention

approval policy evaluation

No other domain may determine whether an approval remains valid.

---

## Authoritative State

Approvals owns:

approval requests

approval decisions

approval history

approval metadata

payload hashes

audit history

approval policies

---

## Public Interfaces

Read:

approval status

approval history

approval details

Write:

request approval

approve

reject

expire

invalidate

---

## Published Events

ApprovalRequested

ApprovalGranted

ApprovalRejected

ApprovalExpired

ApprovalInvalidated

ApprovalPolicyUpdated

---

## Subscribed Events

CapabilityExecutionRequested

IdentityUpdated

ConfigurationUpdated

---

## External Providers

None

Approval decisions remain entirely within Echo.

---

## Consumers

All domains capable of modifying external state.

---

## Repository Ownership

Approvals repositories own:

approval records

audit logs

payload hashes

approval policies

decision history

---

# Capabilities Domain

## Purpose

The Capabilities domain owns Echo's capability metadata.

It describes what Echo is capable of doing.

It does not execute those capabilities.

---

## Owns

Capability Registry

Capability Metadata

Capability Definitions

Capability Discovery

Capability Versioning

Capability Categories

Capability Requirements

Capability Availability

Capability Documentation

Capability Health Metadata

Capability Permissions

---

## Does NOT Own

Business state

Execution

Provider implementations

Portfolio

Projects

Memory

Conversation

Approvals

---

## Business Rules

Capabilities owns:

capability registration

capability discovery

capability metadata

capability versioning

capability compatibility

capability permissions

Capability execution belongs elsewhere.

---

## Authoritative State

Capabilities owns:

registry

metadata

versions

capability definitions

availability metadata

permission metadata

---

## Public Interfaces

Read:

discover capabilities

query capabilities

list capabilities

Write:

register capability

update capability

retire capability

publish capability metadata

---

## Published Events

CapabilityRegistered

CapabilityUpdated

CapabilityRetired

CapabilityAvailabilityChanged

---

## Subscribed Events

SystemInitialized

ProviderConnected

ProviderDisconnected

---

## External Providers

None

Capability ownership remains internal regardless of implementation.

---

## Consumers

Application

Conversation

Projects

Research

All orchestration components

---

## Repository Ownership

Capabilities repositories own:

registry

metadata

version history

permission metadata

compatibility metadata

---

# Knowledge Domain

NOTE

"Knowledge" is the approved bounded-context name for Version 1.0.

Future revisions may adopt a more specific name if the domain evolves beyond curated reference material.

A rename shall require an Architecture Decision Record and shall not change ownership semantics.

## Purpose

The Knowledge domain owns curated reference knowledge used by Echo.

Knowledge represents structured information rather than user-specific memory.

Knowledge is reference material.

Memory is personalized experience.

---

## Owns

Knowledge Articles

Reference Documents

Procedures

Policies

Documentation

Knowledge Categories

Knowledge Indexes

Knowledge Relationships

Knowledge Sources

Knowledge Metadata

Knowledge Version History

Knowledge Search Indexes

---

## Does NOT Own

Durable memory

Conversation history

Research evidence

Portfolio

Projects

Calendar

Emails

Identity

---

## Ownership Boundary

This domain consumes information from other domains through published
contracts, events, or Application orchestration.

Consumption does not imply ownership.

Business ownership remains with the originating domain.

---

## Business Rules

Knowledge owns:

knowledge organization

document categorization

knowledge indexing

reference relationships

knowledge publication

knowledge versioning

Knowledge does not determine business decisions.

---

## Authoritative State

Knowledge owns:

reference documents

knowledge metadata

categories

indexes

relationships

version history

---

## Public Interfaces

Read:

search knowledge

retrieve documents

browse categories

lookup references

Write:

publish document

update document

archive document

categorize document

---

## Published Events

KnowledgePublished

KnowledgeUpdated

KnowledgeArchived

KnowledgeIndexed

---

## Subscribed Events

ProviderSynchronizationCompleted

ApprovalGranted

---

## External Providers

Internal documentation

Imported documentation

Future knowledge providers

Providers contribute information.

Knowledge owns organization.

---

## Consumers

Conversation

Projects

Research

Application

Dashboard

---

## Repository Ownership

Knowledge repositories own:

documents

indexes

metadata

categories

relationships

version history

---

# System Domain

## Purpose

The System domain owns platform operational state.

It exists to monitor, coordinate, and maintain the health of the Echo
platform itself.

The System domain does not own business concepts.

It owns platform operation.

---

## Owns

System Configuration

System Health

Health Checks

Runtime Status

Diagnostics

Telemetry

Metrics

Feature Availability

Error Registry

Operational Logs

Maintenance State

System Alerts

Platform Version

Migration State

---

## Does NOT Own

Portfolio

Research

Calendar

Projects

Email

Memory

Conversation

Knowledge

Identity

Approvals

Capabilities

---

## Business Rules

System owns:

health evaluation

diagnostics

platform monitoring

operational telemetry

migration tracking

runtime validation

system alert generation

feature health

---

## Authoritative State

System owns:

health

metrics

telemetry

diagnostics

runtime status

configuration metadata

operational logs

---

## Public Interfaces

Read:

system status

health

metrics

diagnostics

feature availability

Write:

raise alert

acknowledge alert

update maintenance state

record diagnostic event

---

## Published Events

SystemInitialized

SystemAlertRaised

HealthStatusChanged

DiagnosticsCompleted

FeatureAvailabilityChanged

SystemMaintenanceStarted

SystemMaintenanceCompleted

---

## Subscribed Events

ProviderConnected

ProviderDisconnected

CapabilityRegistered

ConfigurationUpdated

---

## External Providers

Infrastructure

Monitoring Platforms

Logging Platforms

Future observability providers

Providers expose infrastructure.

System owns operational interpretation.

---

## Consumers

Application

Dashboard

Notifications

Operations

---

## Repository Ownership

System repositories own:

telemetry

metrics

diagnostics

runtime status

operational logs

configuration metadata

---

# Cross-Domain Interaction Matrix

The following matrix defines the permitted interactions between business
domains and the mechanism through which each interaction may occur.

A permitted interaction does not transfer ownership.

Ownership always remains with the authoritative owning domain defined by this
document.

| Source Domain | Target Domain | Direct Domain Access | Allowed Mechanism |
|---------------|---------------|----------------------|-------------------|
| Portfolio | Research | No | Application Query |
| Portfolio | Calendar | No | Application Command |
| Portfolio | Email | No | Application Command |
| Portfolio | Notifications | No | Published Domain Event |
| Portfolio | Memory | No | Published Domain Event |
| Portfolio | Conversation | No | Application Query |
| Research | Portfolio | No | Application Query |
| Research | Conversation | No | Application Query |
| Calendar | Notifications | No | Published Domain Event |
| Calendar | Conversation | No | Application Query |
| Email | Notifications | No | Published Domain Event |
| Email | Memory | No | Published Domain Event |
| Projects | Calendar | No | Application Command |
| Projects | Notifications | No | Published Domain Event |
| Conversation | Memory | No | Application Command |
| Memory | Conversation | No | Application Query |
| Any Domain | Approvals | No | Application Command |
| Approvals | Any Domain | No | Published Domain Event |
| Any Domain | Capabilities | No | Application Query |
| System | Notifications | No | Published Domain Event |

Direct domain access is prohibited unless explicitly documented otherwise.

Domains SHALL interact only through:

- Application orchestration
- Published domain events
- Public interfaces

An allowed interaction does not permit access to another domain's internal
state, repositories, business rules, or implementation.

Interaction mechanisms describe communication paths only.

They do not imply ownership, write authority, or implementation dependency.

---

# State Ownership Matrix

The following matrix defines the authoritative owner of each persistent state
category within the system.

No state may exist without exactly one authoritative owner.

| State Category | Authoritative Owner | Read Access | Write Access |
|----------------|---------------------|-------------|--------------|
| Accounts | Portfolio | Authorized Domains | Portfolio |
| Positions | Portfolio | Authorized Domains | Portfolio |
| Holdings | Portfolio | Authorized Domains | Portfolio |
| Transactions | Portfolio | Authorized Domains | Portfolio |
| Cost Basis | Portfolio | Authorized Domains | Portfolio |
| Portfolio Snapshots | Portfolio | Authorized Domains | Portfolio |
| Watchlists | Portfolio | Authorized Domains | Portfolio |
| Investment Policy Statement (IPS) | Portfolio | Authorized Domains | Portfolio |
| IPS Compliance Evaluations | Portfolio | Authorized Domains | Portfolio |
| Rebalancing Proposals | Portfolio | Authorized Domains | Portfolio |
| Portfolio Health Metrics | Portfolio | Authorized Domains | Portfolio |
| Security Master | Research | Authorized Domains | Research |
| Company Profiles | Research | Authorized Domains | Research |
| Valuation Models | Research | Authorized Domains | Research |
| Research Evidence | Research | Authorized Domains | Research |
| News | Research | Authorized Domains | Research |
| Insider Transaction Data | Research | Authorized Domains | Research |
| Congressional Trading Disclosures | Research | Authorized Domains | Research |
| Institutional Ownership Data | Research | Authorized Domains | Research |
| Ownership Change History | Research | Authorized Domains | Research |
| Trading Anomaly Detection Results | Research | Authorized Domains | Research |
| Correlation Analyses | Research | Authorized Domains | Research |
| Research Signals | Research | Authorized Domains | Research |
| Calendar Events | Calendar | Authorized Domains | Calendar |
| Availability | Calendar | Authorized Domains | Calendar |
| Reminders | Calendar | Authorized Domains | Calendar |
| Email Messages | Email | Authorized Domains | Email |
| Email Threads | Email | Authorized Domains | Email |
| Draft Emails | Email | Authorized Domains | Email |
| Durable Memory | Memory | Authorized Domains | Memory |
| Memory Confidence | Memory | Authorized Domains | Memory |
| Active Conversation Context | Conversation | Authorized Domains | Conversation |
| Conversation History | Conversation | Authorized Domains | Conversation |
| Projects | Projects | Authorized Domains | Projects |
| Project Milestones | Projects | Authorized Domains | Projects |
| User Preferences | Identity | Authorized Domains | Identity |
| Connected Accounts | Identity | Authorized Domains | Identity |
| Notification Queue | Notifications | Authorized Domains | Notifications |
| Approval Records | Approvals | Authorized Domains | Approvals |
| Capability Registry | Capabilities | Authorized Domains | Capabilities |
| Knowledge Repository | Knowledge | Authorized Domains | Knowledge |
| System Diagnostics | System | Authorized Domains | System |

The authoritative owner is solely responsible for maintaining the integrity,
consistency, and lifecycle of its owned state.

Other domains may consume state only through approved queries, commands,
events, or public interfaces.

Read access never implies ownership or write authority.

---

# Provider Mapping

Providers integrate external systems into Echo.

Providers never own business concepts.

Business ownership always remains with the corresponding domain.

| Provider | Owning Domain | Responsibility |
|----------|---------------|----------------|
| Schwab | Portfolio | Portfolio synchronization |
| Fidelity | Portfolio | Portfolio synchronization |
| Interactive Brokers | Portfolio | Portfolio synchronization |
| JP Morgan | Portfolio | Portfolio synchronization |
| Vanguard | Portfolio | Portfolio synchronization |
| CSV Import | Portfolio | Portfolio import |
| SEC EDGAR | Research | Regulatory filings |
| Polygon | Research | Market data |
| Financial Modeling Prep | Research | Financial statements |
| Yahoo Finance | Research | Market information |
| Reuters | Research | News |
| Bloomberg | Research | News and market information |
| Reddit | Research | Community sentiment |
| Google Calendar | Calendar | Calendar synchronization |
| Microsoft Outlook | Calendar | Calendar synchronization |
| Apple Calendar | Calendar | Calendar synchronization |
| Gmail | Email | Email synchronization |
| Microsoft 365 | Email | Email synchronization |
| IMAP | Email | Email synchronization |
| Exchange | Email | Email synchronization |
| Google Identity | Identity | Authentication |
| Microsoft Identity | Identity | Authentication |
| Apple Identity | Identity | Authentication |
| Push Notification Services | Notifications | Notification delivery |
| SMS Providers | Notifications | Notification delivery |
| Email Delivery Providers | Notifications | Notification delivery |
| Internal Documentation | Knowledge | Knowledge ingestion |

LLMs, databases, vector stores, caches, queues, and infrastructure services are
implementation details governed by the Application and Provider layers. They do
not constitute business domains and therefore do not appear in this ownership
mapping.

---

# Domain Expansion Rules

Echo's business domains are intentionally stable.

New domains SHALL be introduced only when an existing domain can no longer
maintain a coherent business responsibility.

A new domain SHALL satisfy all of the following:

• owns a distinct business capability

• owns authoritative state

• owns unique business rules

• owns an independent lifecycle

• publishes meaningful business events

• can evolve independently without violating existing ownership boundaries

If these criteria are not met, the capability belongs within an existing
domain.

---

# Domain Split Criteria

Splitting an existing domain is a significant architectural decision.

A split SHALL require an approved Architecture Decision Record (ADR).

A domain should be considered for separation only when one or more of the
following conditions become true:

• multiple independent lifecycles emerge

• unrelated business rules accumulate

• authoritative ownership becomes ambiguous

• deployment or scaling requirements require isolation

• multiple teams could independently own the resulting domains

Technical complexity alone is not sufficient justification for a split.

Premature decomposition is architectural debt.

---

# Dependency Rules

Dependencies shall always point toward ownership.

Consumers depend upon owners.

Owners shall never depend upon consumers.

Circular dependencies between business domains are prohibited.

When two domains require coordination, the Application layer is responsible for
orchestration.

Domains communicate through:

• published events

• public interfaces

• explicit application orchestration

Direct access to another domain's internal implementation is prohibited.

---

# Ownership Violations

The following situations constitute architectural violations.

Shared ownership of a business concept.

Duplicate business rules across domains.

Multiple authoritative copies of the same state.

Persistence outside the owning domain.

Consumers modifying another domain's internal state.

Providers determining business meaning.

Circular ownership relationships.

Business concepts without an owner.

Discovery of an ownership violation SHALL be treated as an architectural defect
and corrected before additional functionality is introduced.

---

# Anti-Patterns

The following patterns are explicitly prohibited.

Portfolio calculating research confidence.

Research modifying portfolio positions.

Calendar maintaining project state.

Email storing durable memories.

Memory scheduling meetings.

Projects sending notifications directly.

Notifications determining business priority.

Approvals executing business operations.

Capabilities executing business logic.

Knowledge storing personalized user memory.

System owning business concepts.

Providers becoming authoritative sources of business truth.

Application becoming a God Object that accumulates business rules or durable
state.

Sharing repositories across business domains.

Sharing write authority across domains.

Multiple domains persisting the same business concept.

If ownership appears shared, the architecture is incorrect.

---

# Amendment Process

This document is normative.

Ownership changes require an approved Architecture Decision Record (ADR).

Changing ownership is considered an architectural change rather than an
implementation change.

All affected documentation shall be updated as part of the same ADR.

Implementation SHALL NOT redefine ownership independently of this document.

---

# Relationship to Other Architecture Documents

This document establishes ownership only.

The remaining architecture documents define how these owners collaborate.

REQUEST_LIFECYCLE.md defines request execution.

CAPABILITY_REGISTRY.md defines capability discovery and contracts.

DOMAIN_EVENTS.md defines event publication and subscription.

APPLICATION_ARCHITECTURE.md defines orchestration.

PROVIDER_ARCHITECTURE.md defines external integrations.

CONSTITUTION.md remains the supreme architectural authority.

---

# Compliance

All implementations SHALL comply with this document.

Code reviews SHOULD verify that:

• business concepts remain within their owning domain

• persistence follows ownership

• business rules are not duplicated

• events originate from their owning domain

• providers remain implementation details

• application orchestration does not accumulate business ownership

Violations SHALL be corrected before architectural approval.

---

# Closing Statement

Echo is organized around ownership rather than technology.

Every business concept has one owner.

Every business rule has one owner.

Every durable record has one owner.

Every provider supports a domain but never replaces it.

Clear ownership enables independent evolution, predictable behavior, and
long-term architectural integrity.

When ownership is unambiguous, implementation becomes significantly simpler.

---