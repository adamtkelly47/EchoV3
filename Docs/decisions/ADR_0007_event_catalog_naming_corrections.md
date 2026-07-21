Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0007: Event Catalog Naming Corrections

## Context

While consolidating DOMAIN_OWNERSHIP.md's per-domain Published/Subscribed event lists into `DOMAIN_EVENTS.md` during Phase 0, four subscriber references were found that did not exactly match any event in a publisher's list (recorded in `DECISION_LOG.md`, 2026-07-20, and flagged rather than silently corrected at the time, since event names are owned by their publishing domain per CONSTITUTION.md's Event Ownership principle). Left unresolved, these would have produced subscribers that silently never fire once the Application layer wires event subscriptions in Phase 5/6.

## Decision

Four corrections to DOMAIN_OWNERSHIP.md:

1. **Projects' published `DeadlineChanged` → `ProjectDeadlineChanged`.** Every other event Projects publishes is prefixed with "Project" (`ProjectCreated`, `ProjectUpdated`, `ProjectCompleted`, `ProjectArchived`) — `DeadlineChanged` was the outlier, and Calendar's subscriber already expected the prefixed form. The publisher's name was brought into line with both its own convention and its subscriber's expectation.

2. **Conversation's subscription to `PortfolioUpdated` → `PortfolioSnapshotCreated`.** No event named `PortfolioUpdated` exists in Portfolio's published list. `PortfolioSnapshotCreated` is the event that actually represents new portfolio state becoming available, which is what Conversation's subscription is for (refreshing conversational context when portfolio data changes).

3. **Projects' subscription to `CalendarEventCompleted` → `CalendarEventUpdated`.** Calendar has no "completed" lifecycle state for events in its Owns/Business Rules sections — only Created, Updated, Deleted. Rather than inventing a new business concept for Calendar to track (which Calendar's domain model doesn't otherwise support), Projects subscribes to `CalendarEventUpdated` and derives "completion" (e.g., an event's end time has passed) from the updated event data at the application layer.

4. **Approvals' subscription to `CapabilityExecutionRequested` removed entirely.** This name is command-shaped ("Requested" — an intention, not a completed fact), which directly conflicts with CONSTITUTION.md's own Event Principles: "Events represent completed business facts. Not intentions. Not commands." Approval evaluation does not need to be event-triggered: REQUEST_LIFECYCLE.md already defines the Approval Checker as a synchronous pipeline stage, invoked directly by application orchestration when evaluating a capability plan. Modeling it as an event subscription would have created a second, redundant trigger path for the same responsibility — itself a Hidden Execution Paths risk. DOMAIN_OWNERSHIP.md's Approvals section now states this explicitly.

## Alternatives Considered

**Add the missing events to their would-be publishers** (e.g., give Calendar a `CalendarEventCompleted` event, give Approvals a real `CapabilityExecutionRequested` event). Rejected for (3) and (4): neither publisher's domain model supports the underlying business concept the event would represent — Calendar doesn't track event completion, and capability-execution-requested is a request, not a fact a domain would ever "publish" after the fact. Adding either would be inventing business concepts to fix a naming bug, which is exactly the speculative-scaffolding risk the Constitution warns against.

**Leave the mismatches flagged and defer resolution to Phase 5/6.** Rejected — cheap to fix now, while these are still just document entries with zero implementation depending on them; the cost only grows once event-subscription code exists.

## Consequences

- `DOMAIN_OWNERSHIP.md` and `DOMAIN_EVENTS.md` are now internally consistent — every subscription in the catalog matches an event some domain actually publishes, with one intentional exception (Approvals' removed subscription, explained inline rather than silently absent).
- No code changes — no domain or application code existed yet to depend on the old names.
- Future domains adding subscriptions should check the publisher's actual event list first; this ADR is a concrete example of why (four mismatches slipped into the original document despite careful drafting).

## Reversal Conditions

If a future phase demonstrates a genuine need for Approvals to react to an asynchronous, event-shaped trigger (as opposed to synchronous pipeline invocation), that would be a new architectural decision made on its own merits — not a reversal of this one, since this ADR's core finding (the original name violated the Event Principles) remains true regardless.
