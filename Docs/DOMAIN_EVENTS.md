Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Domain Events

## Purpose

This document consolidates the event catalog scattered across each domain's Published/Subscribed sections in DOMAIN_OWNERSHIP.md into one reference, and states the delivery mechanism, per CONSTITUTION.md's Domain Events section. DOMAIN_OWNERSHIP.md remains the authoritative source for which domain owns which event; this document exists so the full event graph is visible in one place, since events are a communication boundary, not an API endpoint.

## Delivery Mechanism

Per CONSTITUTION.md's Event Delivery section, the initial implementation uses **synchronous in-process publication**. Event contracts are defined independent of transport so asynchronous or distributed delivery can be introduced later via ADR if operationally justified. No message broker (Redis Streams, Kafka, etc.) is scaffolded before that need is demonstrated — doing so now would violate the No Future Scaffolding Rule.

## Event Principles

Events represent completed business facts, not intentions or commands. They are immutable, versioned, and carry sufficient context for downstream consumers. The originating domain owns the event definition; consumers may subscribe but may not redefine it.

## Event Catalog

| Domain | Publishes | Subscribes To |
|---|---|---|
| Portfolio | PortfolioImported, PortfolioSynchronized, PortfolioSnapshotCreated, PortfolioSnapshotArchived, PortfolioReconciled, PositionCreated, PositionClosed, HoldingUpdated, WatchlistUpdated, IPSUpdated, IPSComplianceEvaluated, PortfolioHealthUpdated, RebalancingProposalCreated | ApprovalGranted, ApprovalRejected, ProviderSynchronizationCompleted, IdentityUpdated |
| Research | ResearchCompleted, ResearchEvidenceUpdated, SecurityMasterUpdated, NewsIngested, ThesisUpdated, CatalystDetected, ResearchConfidenceChanged, MarketDataUpdated, InsiderActivityDetected, CongressionalTradeDetected, TradingAnomalyDetected, OwnershipTrendUpdated, ResearchSignalGenerated | PortfolioSnapshotCreated, ProviderSynchronizationCompleted, ScheduledResearchRequested |
| Calendar | CalendarEventCreated, CalendarEventUpdated, CalendarEventDeleted, ReminderScheduled, ReminderTriggered, AvailabilityChanged, CalendarSynced | ApprovalGranted, ProjectDeadlineChanged, IdentityUpdated |
| Email | EmailIndexed, EmailReceived, EmailSent, DraftCreated, DraftUpdated, EmailClassified, InboxChanged | ApprovalGranted, IdentityUpdated, ProviderSynchronizationCompleted |
| Memory | MemoryCreated, MemoryUpdated, MemoryArchived, MemoryDeleted, MemoryPromoted, MemoryConfidenceChanged, MemoryConflictDetected | ConversationCompleted, ApprovalGranted, IdentityUpdated, ProjectCompleted |
| Conversation | ConversationStarted, ConversationCompleted, ConversationSummarized, ConversationArchived, IntentResolved | MemoryUpdated, PortfolioSnapshotCreated, ResearchCompleted, ProjectUpdated, NotificationDelivered |
| Projects | ProjectCreated, ProjectUpdated, ProjectCompleted, MilestoneCompleted, ProjectArchived, ProjectDeadlineChanged | CalendarEventUpdated, ApprovalGranted, ConversationCompleted, MemoryUpdated |
| Identity | IdentityUpdated, PreferenceChanged, ProviderConnected, ProviderDisconnected, ConfigurationUpdated | ApprovalGranted |
| Notifications | NotificationQueued, NotificationDelivered, NotificationFailed, NotificationAcknowledged, NotificationExpired | PortfolioHealthUpdated, IPSComplianceEvaluated, CalendarEventCreated, ReminderTriggered, EmailReceived, ProjectCompleted, ResearchCompleted, SystemAlertRaised |
| Approvals | ApprovalRequested, ApprovalGranted, ApprovalRejected, ApprovalExpired, ApprovalInvalidated, ApprovalPolicyUpdated | IdentityUpdated, ConfigurationUpdated |
| Capabilities | CapabilityRegistered, CapabilityUpdated, CapabilityRetired, CapabilityAvailabilityChanged | SystemInitialized, ProviderConnected, ProviderDisconnected |
| Knowledge | KnowledgePublished, KnowledgeUpdated, KnowledgeArchived, KnowledgeIndexed | ProviderSynchronizationCompleted, ApprovalGranted |
| System | SystemInitialized, SystemAlertRaised, HealthStatusChanged, DiagnosticsCompleted, FeatureAvailabilityChanged, SystemMaintenanceStarted, SystemMaintenanceCompleted | ProviderConnected, ProviderDisconnected, CapabilityRegistered, ConfigurationUpdated |

Approval evaluation is not event-triggered — see the note under Approvals in `DOMAIN_OWNERSHIP.md` and ADR_0007.

## Resolved Inconsistencies

Four subscription references were found, while first consolidating this catalog, that didn't exactly match any event in a publisher's list. All four are now resolved in `DOMAIN_OWNERSHIP.md` and reflected in the table above — see `Docs/decisions/ADR_0007_event_catalog_naming_corrections.md` for the reasoning behind each:

1. Calendar subscribed to `ProjectDeadlineChanged`; Projects published `DeadlineChanged`. Fixed by renaming the publisher's event to `ProjectDeadlineChanged`, matching the naming convention every other Projects event already follows (`ProjectCreated`, `ProjectUpdated`, `ProjectCompleted`, `ProjectArchived`).
2. Conversation subscribed to `PortfolioUpdated`, which didn't exist. Fixed by subscribing to `PortfolioSnapshotCreated` — the event that actually represents new portfolio state becoming available.
3. Projects subscribed to `CalendarEventCompleted`, which didn't exist (Calendar has no "completed" concept for events). Fixed by subscribing to `CalendarEventUpdated`; Projects can derive completion (e.g. past end time) from the updated event data at the application layer rather than Calendar inventing a new lifecycle state it doesn't otherwise track.
4. Approvals subscribed to `CapabilityExecutionRequested`, which is command-shaped ("Requested"), not a completed business fact — a direct conflict with this document's own Event Principles. Fixed by removing the subscription: approval evaluation is invoked synchronously by the Application layer's Approval Checker pipeline stage (`REQUEST_LIFECYCLE.md`), not by a domain event.

## Anonymous Events Prohibition

Every event name is a specific past-tense business fact (e.g. `PortfolioSnapshotCreated`, not `EventOccurred` or `SomethingChanged`), per the Constitution's Anonymous Events anti-pattern. All entries in the catalog above already satisfy this; new events must follow the same convention.

## Versioning

Events are versioned contracts. A breaking change to an event's shape requires a version increment and is documented as a material deviation (CONTRIBUTING.md), not a silent change.
