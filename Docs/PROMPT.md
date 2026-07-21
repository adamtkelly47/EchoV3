# Echo Personal AI Operating System

## Architecture Specification and Sequential Build Plan

You are acting as the principal software architect and senior implementation engineer for a complete rebuild of Echo, a private personal AI operating system.

This is the third attempt at the project. Previous attempts became disorganized, overly coupled, difficult to reason about, and insufficiently grounded in real tool capability. This rebuild must prioritize architectural clarity, testability, source traceability, safety, and disciplined file organization before feature volume.

Do not begin by writing feature code.

First inspect the repository, establish the architecture, create the required design documents, and verify that the foundation is coherent. Every implementation phase must be narrow, testable, and complete before the next phase begins.

The system must be understandable to a highly experienced software engineer who has never seen the project before. A competent engineer should be able to determine what each directory owns, how data moves through the system, where decisions are made, how actions are authorized, and how failures are handled without reverse engineering the entire codebase.

# 1. Product Definition

Echo is a private personal AI assistant and personal operating system.

Its long term role is to:

1. Understand the user, preferences, goals, projects, accounts, schedule, communications, and decision patterns over time.

2. Provide direct conversational assistance through a consistent interface.

3. Read and analyze real personal data from authorized integrations.

4. Perform deterministic calculations in code.

5. Conduct research using attributable sources.

6. Challenge unsupported assumptions and weak reasoning.

7. Propose consequential actions without autonomously executing them.

8. Eventually monitor selected conditions proactively.

9. Eventually support voice interaction.

10. Expand to future capabilities without requiring architectural reconstruction.

Echo is not:

1. A generic chatbot wrapper.

2. A collection of disconnected agents.

3. A system where the language model invents calculations.

4. A system where a model can directly invoke consequential write operations.

5. A dashboard that merely displays raw API data.

6. A financial trading bot.

7. An autonomous decision maker.

# 2. User Context

The user is a finance senior with an accounting minor and wealth management experience.

The user understands product direction, investment logic, and high level architecture, but has limited coding experience and relies heavily on AI for implementation.

Implementation communication must therefore be:

1. Technically rigorous.

2. Explicit about major architectural decisions.

3. Clear about unfamiliar concepts when they first appear.

4. Lean during ordinary build work.

5. Honest about uncertainty and limitations.

6. Resistant to unnecessary complexity.

The assistant must push back when a requested shortcut damages correctness, safety, maintainability, or long term architecture.

# 3. Nonnegotiable System Principles

## 3.1 Verified truth only

Echo must not present a factual claim, number, date, quote, position value, account balance, event, email detail, market price, or research result unless it can identify the source from which the information came.

Every externally derived fact must carry provenance.

At minimum, provenance should support:

1. Source system.

2. Retrieval time.

3. Relevant account, document, endpoint, or record identifier.

4. Data freshness.

5. Transformation history when the value was computed.

6. Confidence or validation state when applicable.

If information cannot be verified, Echo must say that it could not be verified.

Negative claims require verification too. Echo may not say that something does not exist, is unavailable, or is impossible without checking the appropriate tool or source when such verification is possible.

## 3.2 Deterministic computation

All arithmetic, financial calculations, allocation calculations, performance calculations, date calculations, thresholds, aggregations, reconciliations, and rule evaluations must occur in deterministic code.

Language models may:

1. Explain computed results.

2. Identify which calculation is needed.

3. Interpret a completed calculation.

4. Recommend further analysis.

Language models may not:

1. Perform authoritative arithmetic mentally.

2. Manufacture missing numbers.

3. Substitute prose for computation.

4. Estimate an account value when exact account data should exist.

## 3.3 Human approval for consequential actions

Any operation that sends, writes, deletes, modifies, publishes, trades, transfers, schedules, cancels, archives, labels, or otherwise changes an external system must use the same action workflow:

1. Propose.

2. Validate.

3. Present for review.

4. Approve, edit, or reject.

5. Execute only after valid approval.

6. Verify the external result.

7. Record an audit event.

The assistant may never approve its own proposal.

A user message such as “send this now” may authorize creation of a proposal, but must not bypass the review object and approval mechanism.

Approval must bind to the exact action payload. Any material edit invalidates prior approval and requires a new approval.

## 3.4 Read before write

Every integration begins in read only mode.

Write support may be added only after:

1. Read behavior is stable.

2. Data mappings are tested.

3. Failure handling is tested.

4. Permissions are minimized.

5. The approval workflow is integrated.

6. The write scope is narrow and explicitly documented.

## 3.5 Interface parity

Web chat, dashboard actions, command line development tools, future mobile interfaces, and future voice interfaces must call the same application APIs.

No business capability may exist only inside one user interface.

The interface layer may render capabilities differently, but it may not reimplement capability logic.

## 3.6 Cost discipline

Local and free resources are preferred.

Hosted Claude usage must be reserved for work that materially benefits from advanced reasoning or direct high quality conversation.

Claims about provider pricing, limits, data coverage, or free access must not be trusted from marketing text alone. Provider evaluation must include a live verification procedure before adoption.

## 3.7 Replaceability

External services and model providers must sit behind interfaces.

Echo must be able to replace:

1. Claude with another hosted model.

2. Ollama with another local inference server.

3. Redis Streams with another queue or event system.

4. A financial data provider with another provider.

5. A vector storage implementation.

6. Authentication providers.

Core domain logic must not depend directly on vendor specific response formats.

# 4. Core Architectural Decision

Build Echo as a modular application core with a small number of operationally justified containers.

Do not begin with dozens of microservices.

The initial architecture should use:

1. One backend application container.

2. One asynchronous worker container using the same application codebase.

3. One scheduler container using the same application codebase.

4. One frontend container.

5. Neon serverless Postgres.

6. Redis.

7. Ollama.

8. Optional observability containers only when the relevant phase is reached.

The backend, worker, and scheduler are separate runtime processes but belong to the same codebase and use the same domain modules.

This is a modular monolith with isolated execution roles.

This gives Echo:

1. Clear module ownership.

2. Transactional consistency.

3. Easier testing.

4. Lower operational burden.

5. A clean path to extract a module into a separate service later if actual scale, security, reliability, or deployment requirements justify it.

No module should be extracted into its own deployable service merely because it represents a product feature.

# 5. Container Architecture

## 5.1 Frontend container

Responsibilities:

1. Render the dashboard.

2. Render chat.

3. Display source citations and freshness.

4. Display approval proposals.

5. Make approval actions unmistakable.

6. Display system health and integration status.

7. Communicate only with the backend API.

The frontend must contain no authoritative business logic.

Recommended initial technology:

1. TypeScript.

2. React.

3. A production capable framework such as Next.js, provided the chosen structure does not blur frontend and backend ownership.

4. A typed API client generated from or validated against the backend contract.

## 5.2 Backend application container

Responsibilities:

1. Authentication and authorization.

2. Conversation orchestration.

3. Capability routing.

4. Read tool invocation.

5. Approval proposal creation.

6. Approval validation.

7. Domain service execution.

8. API contracts.

9. Retrieval of stored state.

10. Streaming conversational responses.

11. Audit logging coordination.

Recommended initial technology:

1. Python.

2. FastAPI.

3. Pydantic.

4. SQLAlchemy or SQLModel with Alembic migrations.

5. Strict typing and static analysis.

The backend must not perform long running bulk processing inside request handlers.

## 5.3 Worker container

Responsibilities:

1. Asynchronous research ingestion.

2. News classification.

3. Document parsing.

4. Local model batch processing.

5. Portfolio snapshots.

6. Email indexing.

7. Historical data refreshes.

8. Anomaly detection.

9. Embedding generation.

10. Retryable external API calls.

11. Post execution verification jobs.

The worker must consume typed job definitions.

A job must have:

1. Job type.

2. Version.

3. Input schema.

4. Idempotency key.

5. Retry policy.

6. Timeout.

7. Provenance requirements.

8. Output schema.

9. Failure classification.

## 5.4 Scheduler container

Responsibilities:

1. Trigger periodic jobs.

2. Maintain schedule definitions.

3. Prevent duplicate scheduled execution.

4. Observe quiet hours and user preferences.

5. Trigger monitoring evaluations.

6. Never directly execute consequential user actions.

The scheduler creates jobs. It does not perform domain work itself.

## 5.5 Neon database container

The user explicitly wants Neon to be used as the database. Neon serverless Postgres is the authoritative state store.

It should hold:

1. Users.

2. Conversations.

3. Messages.

4. Model calls.

5. Tool calls.

6. Source records.

7. Integrations.

8. Credentials metadata.

9. Account metadata.

10. Portfolio snapshots.

11. Holdings snapshots.

12. Calendar event cache.

13. Email metadata cache.

14. Research entities.

15. Documents.

16. Memory records.

17. Approval proposals.

18. Approval decisions.

19. Action executions.

20. Audit events.

21. Jobs.

22. Notifications.

23. IPS documents and rule definitions.

Do not use a vector database as the system of record.

Vector search is an index over authoritative records, not the authoritative record itself.

Use PostgreSQL vector capabilities initially unless scale or performance later justifies a separate vector store.

## 5.6 Redis container

Redis should be used for ephemeral and coordination workloads only.

Initial responsibilities:

1. Job queue transport.

2. Distributed locks.

3. Rate limiting.

4. Short lived caches.

5. Streaming partial responses.

6. Event notifications.

7. Scheduler coordination.

Redis must not become the sole home of durable user data.

## 5.7 Ollama container

Ollama hosts one or more local models.

The local model is treated as an untrusted inference processor.

It may assist with:

1. Classification.

2. Extraction.

3. Normalization.

4. Summarization.

5. Ranking.

6. Deduplication suggestions.

7. Entity matching suggestions.

8. Bulk data reduction.

Its outputs must be schema validated and, when appropriate, checked against deterministic rules.

The local model must not directly execute tools or actions.

## 5.8 Claude API

Claude is an external reasoning provider accessed through a model gateway inside the backend application.

Claude should be used for:

1. Direct conversation with the user.

2. Complex synthesis across domains.

3. Strategic reasoning.

4. Ambiguous judgment.

5. Challenging a user thesis.

6. Research conclusions after local preprocessing.

7. High stakes explanation.

8. Deciding which approved read capabilities are needed for a request.

Claude must not directly receive secrets or unrestricted raw system access.

# 6. Communication Map

The normal flow should be:

User interface to backend API.

Backend API to application orchestration layer.

Application orchestration layer to domain services.

Domain services to integration adapters or repositories.

Integration adapters to external systems.

Repositories to Neon.

Long running work to Redis queue.

Worker to domain services and adapters.

Worker to Ollama when local inference is appropriate.

Backend to Claude through the model gateway when hosted reasoning is justified.

All significant operations emit structured audit events.

Internal communication should use typed Python interfaces and domain objects inside the codebase.

External and asynchronous boundaries must use versioned schemas.

Do not pass arbitrary dictionaries across module boundaries when a typed model can be defined.

# 7. Domain Modules

Organize the application by business capability, not by technical layer alone.

Use a structure similar to:

```text
echo/
    apps/
        api/
        worker/
        scheduler/
    core/
        config/
        errors/
        logging/
        security/
        time/
        identifiers/
        provenance/
        events/
        observability/
    domains/
        conversation/
        approvals/
        actions/
        integrations/
        portfolio/
        research/
        calendar/
        email/
        memory/
        documents/
        notifications/
        projects/
        identity/
    providers/
        models/
            claude/
            ollama/
        brokerage/
            schwab/
        calendar/
            google/
        email/
            gmail/
        research/
            sec/
            congressional/
            market_data/
            fundamentals/
            news/
    infrastructure/
        database/
        queue/
        cache/
        secrets/
        http/
    api/
        routes/
        schemas/
        dependencies/
        middleware/
    tests/
        unit/
        integration/
        contract/
        end_to_end/
        fixtures/
        architecture/
    scripts/
    docs/
    migrations/
```

Each domain should usually contain:

```text
domain_name/
    models.py
    schemas.py
    repository.py
    service.py
    policies.py
    events.py
    errors.py
    interfaces.py
```

Create additional files only when the responsibility is real and distinct.

Do not create empty abstraction files merely to imitate an architectural pattern.

# 8. Dependency Rules

Enforce these dependency directions:

1. API routes may depend on application and domain services.

2. Domain services may depend on domain interfaces.

3. Provider adapters may implement domain interfaces.

4. Infrastructure may implement repository, queue, cache, or secret interfaces.

5. Domain modules must not import frontend code.

6. Domain modules must not import FastAPI route objects.

7. Domain modules must not import vendor specific SDK response classes.

8. The portfolio domain must not import the Gmail adapter.

9. The email domain must not import the Schwab adapter.

10. Cross domain workflows must be coordinated through application services or domain events, not direct hidden coupling.

Add automated architecture tests to prevent forbidden imports.

# 9. File and Function Discipline

The user supplied the following hard requirement:

No function may exceed 500 lines.

Treat this as an absolute maximum, not a target.

Use stricter engineering thresholds:

1. Preferred function size: under 50 lines.

2. Review warning: over 100 lines.

3. Strong refactor warning: over 150 lines.

4. Architecture review required: over 300 lines.

5. Build failure: over 500 lines.

For files:

1. Preferred file size: under 500 lines.

2. Review warning: over 800 lines.

3. Strong refactor warning: over 1,500 lines.

4. Architecture review required: over 3,000 lines.

5. User supplied soft ceiling: 10,000 lines.

A 9,000 line file is technically below the user ceiling but architecturally unacceptable without exceptional justification.

Use automated checks for:

1. Function length.

2. File length.

3. Cyclomatic complexity.

4. Import cycles.

5. Type checking.

6. Dead code.

7. Duplicate code.

8. Formatting.

9. Test coverage.

10. Security scanning.

Recommended tools may include Ruff, Black if still necessary alongside Ruff, MyPy or Pyright, Pytest, Coverage, Radon, Vulture, Bandit, and Semgrep. Confirm current compatibility before committing.

# 10. Request Orchestration

Do not build routing as a growing list of keyword rules.

Use an explicit capability registry.

Every capability definition should identify:

1. Capability name.

2. Version.

3. Description.

4. Input schema.

5. Output schema.

6. Required permissions.

7. Read or write classification.

8. Whether approval is required.

9. Suitable execution environment.

10. Timeout.

11. Idempotency behavior.

12. Provenance requirements.

13. Error types.

14. User visible explanation.

Example capability categories:

1. Read current time.

2. Search calendar.

3. Read portfolio positions.

4. Calculate allocation.

5. Search email.

6. Research a security.

7. Draft an email proposal.

8. Propose a calendar event.

9. Execute an approved calendar event.

10. Send an approved email.

The orchestrator may select capabilities, but capability policy determines whether they may run.

The model does not decide its own permissions.

# 11. Approval Architecture

Approval gating is a cross cutting platform capability, not custom logic implemented separately inside Calendar, Gmail, trading, or future integrations.

## 11.1 Action proposal

Every consequential operation must first create an immutable action proposal.

An action proposal should include:

1. Proposal identifier.

2. User identifier.

3. Action type.

4. Action schema version.

5. Human readable summary.

6. Full normalized payload.

7. External target system.

8. Expected effect.

9. Risk level.

10. Required permission.

11. Creation time.

12. Expiration time.

13. Proposal creator.

14. Validation results.

15. Warnings.

16. Source context.

17. Payload hash.

18. Current status.

## 11.2 Proposal states

Use a strict state machine such as:

1. Draft.

2. Validated.

3. Awaiting approval.

4. Approved.

5. Rejected.

6. Expired.

7. Executing.

8. Executed.

9. Verification failed.

10. Execution failed.

11. Cancelled.

Invalid state transitions must be rejected in code.

## 11.3 Approval binding

Approval must bind to:

1. Proposal identifier.

2. Payload hash.

3. User identifier.

4. Approval time.

5. Expiration time.

6. Optional confirmation challenge for higher risk actions.

If the payload changes after approval, the hash changes and approval becomes invalid.

## 11.4 Execution separation

Proposal creation and action execution must be separate functions and separate capability definitions.

The model may call proposal creation.

The model may not call an execution capability unless the backend has independently verified a valid user approval.

Execution capability inputs must not accept a raw arbitrary payload from the model.

They should accept an approved proposal identifier. The execution service then loads the stored immutable payload.

## 11.5 Idempotency

Every action execution must have an idempotency key.

Retries must not create duplicate calendar events, duplicate emails, duplicate transfers, or duplicate trades.

## 11.6 Verification

After execution, Echo must verify the external result when possible.

Examples:

1. Requery Google Calendar and confirm the event exists.

2. Requery Gmail and confirm the message identifier and sent state.

3. For future trades, confirm the broker accepted the order and report the broker order identifier and status.

Execution success means verified external effect, not merely an HTTP 200 response.

# 12. Model Gateway and Division of Labor

Create a single model gateway with provider adapters.

The application should not call Claude or Ollama SDKs directly outside the provider layer.

## 12.1 Local model default workloads

Prefer Ollama for:

1. Parsing raw text into a defined schema.

2. Categorizing news.

3. Scoring likely relevance.

4. Extracting entities.

5. Converting API responses into normalized candidate records.

6. Summarizing batches of articles.

7. Grouping duplicate stories.

8. Extracting claims from documents.

9. Identifying possible anomalies for deterministic review.

10. Producing compact context packages for Claude.

11. Classifying emails.

12. Drafting low risk first pass summaries.

13. Memory candidate extraction.

14. Document chunk labeling.

15. Historical transaction feature generation.

16. Bulk watchlist screening.

Local inference outputs must be treated as candidate analysis rather than verified truth.

## 12.2 Claude workloads

Prefer Claude for:

1. Direct user conversation.

2. Cross domain synthesis.

3. Complicated investment thesis evaluation.

4. Reasoned pushback.

5. Planning.

6. Decision support.

7. Interpreting conflicting evidence.

8. Producing final research narratives.

9. Determining what information is missing.

10. Handling novel user requests.

11. High quality drafting when wording matters.

12. Deciding whether local model output is sufficient or requires escalation.

## 12.3 Deterministic code workloads

Use normal code, not either model, for:

1. Arithmetic.

2. Portfolio calculations.

3. Date and time calculations.

4. Threshold evaluations.

5. IPS rule checks.

6. Duplicate record detection when exact identifiers exist.

7. Schema validation.

8. Permission enforcement.

9. Approval state transitions.

10. Audit records.

11. Account reconciliation.

12. Data freshness checks.

13. Rate limiting.

14. Retry behavior.

15. Security rules.

16. Source ranking rules that can be explicitly encoded.

## 12.4 Escalation policy

Implement a model task policy that considers:

1. Task type.

2. Stakes.

3. Ambiguity.

4. Required reasoning depth.

5. Data sensitivity.

6. Token volume.

7. Local model confidence.

8. Schema validation success.

9. Cost budget.

10. User preference.

A local task should escalate to Claude when:

1. Required schema validation repeatedly fails.

2. The task involves material judgment.

3. Evidence conflicts.

4. The local model expresses low confidence.

5. The task affects a consequential recommendation.

6. The user is directly conversing and expects a polished response.

7. The local output would expose the user to meaningful financial, legal, reputational, or operational risk.

Track model usage, latency, cost estimates, failure rates, and escalation rates.

Do not assume local inference is cheaper in every practical sense. Measure hardware utilization, latency, quality, and retry frequency.

# 13. Time Handling

Create a dedicated clock abstraction.

Business logic must not call the system clock directly.

The clock service must provide:

1. Current UTC time.

2. User local time.

3. Timezone conversion.

4. Test clock support.

5. Monotonic timing where appropriate.

6. Data freshness calculations.

Current time must be refreshed when needed rather than assumed from conversation start.

Store timestamps in UTC.

Display timestamps in the user timezone.

# 14. Provenance Architecture

Every normalized data object derived from an external system should be connectable to one or more source records.

Create a source record model with fields such as:

1. Source type.

2. Provider.

3. Retrieval time.

4. Original endpoint or document.

5. External identifier.

6. Request parameters.

7. Response content hash.

8. Data effective time.

9. Freshness policy.

10. Storage location for permitted raw data.

11. Parsing version.

12. Validation status.

13. Error state.

Computed values should record:

1. Calculation name.

2. Calculation version.

3. Input record identifiers.

4. Execution time.

5. Output.

6. Rounding policy.

7. Validation result.

This enables Echo to answer, “Where did that number come from?”

# 15. Memory Architecture

Memory must not be an undifferentiated vector store of conversation fragments.

Use layered memory:

## 15.1 Conversation memory

Recent messages needed for conversational continuity.

## 15.2 Durable user facts

Explicit, stable facts such as preferences, goals, account relationships, and persistent constraints.

## 15.3 Episodic memory

Important prior decisions, events, and outcomes.

## 15.4 Project memory

Project goals, current status, decisions, tasks, risks, and documents.

## 15.5 Procedural memory

Approved recurring methods and workflows.

## 15.6 Inferred memory candidates

Possible preferences or patterns extracted by a model but not yet promoted to durable truth.

Every memory record should include:

1. Content.

2. Type.

3. Source.

4. Creation time.

5. Last verified time.

6. Confidence.

7. Sensitivity classification.

8. Expiration or review policy.

9. Supersession relationship.

10. Whether the user explicitly confirmed it.

Memory retrieval should combine:

1. Exact structured filtering.

2. Recency.

3. Importance.

4. Semantic similarity.

5. Project context.

6. Source reliability.

The model may suggest memory candidates.

Promotion, updating, conflict resolution, and deletion must occur through explicit memory services.

# 16. Portfolio Architecture

Schwab is the sole source of truth for real account balances and holdings.

The portfolio domain should separate:

1. Brokerage account identity.

2. Raw Schwab responses.

3. Normalized account snapshots.

4. Position snapshots.

5. Security master records.

6. Market price records.

7. Calculated exposures.

8. Performance calculations.

9. IPS rule checks.

10. Research conclusions.

A research data provider must never overwrite the current real Schwab position value.

Use immutable snapshots for historical tracking.

Every snapshot should record:

1. Account identifier.

2. Retrieval time.

3. Data effective time.

4. Cash.

5. Buying power where applicable.

6. Positions.

7. Quantities.

8. Prices.

9. Market values.

10. Cost basis when supplied.

11. Source identifiers.

12. Reconciliation result.

13. Partial data warnings.

Portfolio calculations must define exact methodologies.

Examples:

1. Total market value.

2. Asset allocation.

3. Account concentration.

4. Security concentration.

5. Sector exposure.

6. Geographic exposure.

7. Unrealized gain or loss.

8. Time weighted performance when data supports it.

9. Money weighted performance when cash flow data supports it.

Do not label a calculation as performance unless the required data exists.

# 17. Investment Policy Statement Architecture

An IPS is a versioned domain document, not freeform prompt text alone.

Each IPS should support:

1. Account scope.

2. Strategy name.

3. Objective.

4. Time horizon.

5. Liquidity needs.

6. Risk tolerance.

7. Constraints.

8. Allowed asset classes.

9. Target allocations.

10. Minimum and maximum ranges.

11. Concentration limits.

12. Restricted securities.

13. Rebalancing policy.

14. Tax considerations.

15. Benchmark.

16. Review schedule.

17. Effective date.

18. Version history.

Rules should be machine evaluable where possible.

Echo may flag:

1. Allocation drift.

2. Concentration.

3. Restricted holdings.

4. Liquidity mismatch.

5. Strategy inconsistency.

6. Missing data.

Echo must not automatically rebalance.

# 18. Research Architecture

Research should be entity centered and evidence based.

A security research package should support:

1. Security identity.

2. Quote data.

3. Historical prices.

4. Fundamentals.

5. Earnings history.

6. Valuation metrics.

7. Analyst estimates and ratings.

8. Company filings.

9. Relevant news.

10. Insider transactions.

11. Congressional disclosures.

12. Thesis statements.

13. Risks.

14. Catalysts.

15. Contradictory evidence.

16. Source freshness.

17. Missing data.

Separate collection from interpretation.

Collection pipeline:

1. Fetch.

2. Store source record.

3. Normalize.

4. Validate.

5. Deduplicate.

6. Enrich.

7. Score relevance.

8. Build evidence package.

9. Synthesize.

No final research conclusion should rely solely on a local model relevance score.

## 18.1 Insider anomaly detection

Do not ask a model to simply declare a transaction anomalous.

Build features in code such as:

1. Transaction value.

2. Transaction size relative to the insider’s prior transactions.

3. Transaction size relative to compensation or ownership when available.

4. Open market purchase versus grant, option exercise, tax sale, or planned sale.

5. Number of insiders acting in a time window.

6. Role seniority.

7. Historical timing relative to earnings or major events.

8. Change in beneficial ownership.

Use deterministic features to produce anomaly candidates.

Use the local model to classify filing context and explain candidate patterns.

Use Claude only for final interpretation when the evidence warrants it.

## 18.2 Congressional transaction analysis

Normalize:

1. Politician identity.

2. Chamber.

3. Committee assignments.

4. Filing date.

5. Transaction date.

6. Asset.

7. Value range.

8. Transaction type.

9. Sector.

10. Issuer.

11. Filing delay.

Potential anomaly features may include:

1. Trade size relative to that politician’s history.

2. Sector concentration.

3. Timing relative to committee activity.

4. Timing relative to legislation, hearings, or regulatory events.

5. Repeated related trades.

6. Household activity patterns.

Never state improper conduct merely from correlation.

The system should describe the observed relationship and its limitations.

# 19. News Architecture

News relevance should be scored against the user’s actual context.

Inputs may include:

1. Current holdings.

2. Watchlist.

3. IPS.

4. Active investment theses.

5. Projects.

6. Career interests.

7. Selected global topics.

8. Calendar context.

9. Previously dismissed stories.

Candidate scoring may consider:

1. Direct entity match.

2. Financial materiality.

3. Source quality.

4. Novelty.

5. Event type.

6. Geographic relevance.

7. Portfolio exposure.

8. Thesis relevance.

9. Time sensitivity.

10. Duplicate story clustering.

11. User feedback history.

The local model may classify and summarize.

Deterministic code should enforce source rules, deduplication identifiers, freshness windows, portfolio matching, and suppression logic.

Claude should synthesize only the small set that survived filtering.

Trending status alone is never an investment signal.

# 20. Calendar Architecture

Begin with read only Google Calendar integration.

Read capabilities should include:

1. List calendars.

2. Search events.

3. Read event details.

4. Understand recurring series and individual instances.

5. Determine free and busy windows.

6. Display timezone correctly.

Write capabilities must later use approval proposals for:

1. Create event.

2. Modify event.

3. Delete event.

4. Respond to invitation.

5. Modify recurring event series.

Recurring event changes must clearly state whether the action affects:

1. One occurrence.

2. This and following occurrences.

3. The entire series.

# 21. Email Architecture

Begin with read only Gmail integration.

Read capabilities should include:

1. Search.

2. Read message.

3. Read thread.

4. Read attachments under explicit safety rules.

5. Categorize.

6. Identify action items.

7. Summarize threads.

8. Detect messages needing a response.

Later write capabilities must use approval proposals for:

1. Create draft.

2. Update draft.

3. Send message.

4. Send reply.

5. Forward message.

6. Archive.

7. Apply labels.

8. Delete or move to trash.

The approval screen must show:

1. Recipients.

2. Carbon copy recipients.

3. Blind carbon copy recipients.

4. Subject.

5. Complete body.

6. Attachments.

7. Thread context.

8. Exact operation.

Sending must never occur from a partial preview.

# 22. Dashboard Product Architecture

The initial dashboard should focus on immediate state, not maximum feature density.

Primary sections:

1. Today.

2. Money.

3. Attention.

4. Projects.

5. Conversation.

## 22.1 Today

Show:

1. Current date and local time.

2. Upcoming events.

3. Schedule conflicts.

4. Time sensitive tasks.

5. Relevant unread communications.

## 22.2 Money

Show:

1. Last verified Schwab sync time.

2. Total account values.

3. Daily change only when authoritative data supports it.

4. Largest positions.

5. Concentration warnings.

6. IPS drift.

7. Data freshness warnings.

## 22.3 Attention

Show:

1. Approval requests.

2. Failed integrations.

3. Important news.

4. Emails likely requiring action.

5. Monitoring alerts.

## 22.4 Projects

Show:

1. Active projects.

2. Current milestone.

3. Blockers.

4. Next action.

5. Recent decisions.

## 22.5 Conversation

Provide a natural conversational interface.

The chat must be able to use every capability available elsewhere in the interface.

# 23. Security Architecture

Security must be designed before real integrations are connected.

Requirements:

1. Use least privilege OAuth scopes.

2. Encrypt secrets at rest.

3. Never store access tokens in source control.

4. Keep secrets out of logs.

5. Redact sensitive payloads from model calls unless required.

6. Define data retention policies.

7. Record access and action audits.

8. Separate development credentials from production credentials.

9. Use secure cookies or equivalent session handling.

10. Protect against cross site request forgery.

11. Validate redirect addresses.

12. Rate limit sensitive endpoints.

13. Require reauthentication or stronger confirmation for future high risk actions.

14. Scan dependencies.

15. Pin dependency versions.

16. Maintain an incident response document.

17. Back up PostgreSQL.

18. Test restoration.

19. Do not expose Ollama, PostgreSQL, or Redis publicly.

20. Route private service communication through an internal Docker network.

# 24. Error Model

Define a common error taxonomy.

Examples:

1. Authentication error.

2. Authorization error.

3. Validation error.

4. Integration unavailable.

5. Rate limited.

6. Source stale.

7. Source incomplete.

8. Schema mismatch.

9. Model output invalid.

10. Approval required.

11. Approval expired.

12. Proposal changed.

13. Execution uncertain.

14. Verification failed.

15. Retry exhausted.

16. Configuration error.

17. Internal invariant violation.

Errors must have:

1. Stable machine code.

2. Safe user message.

3. Internal diagnostic detail.

4. Retry classification.

5. Correlation identifier.

6. Severity.

Do not expose stack traces or secrets to the user.

# 25. Observability

Use structured logging from the beginning.

Every request, job, model call, tool call, proposal, approval, and execution should have correlation identifiers.

Track:

1. Request latency.

2. Job latency.

3. Queue depth.

4. Tool success rate.

5. Provider rate limits.

6. Model latency.

7. Model token usage.

8. Hosted model cost estimates.

9. Local model processing volume.

10. Escalation rate from local to hosted models.

11. Approval conversion rate.

12. Integration freshness.

13. Failed verification count.

14. Retry count.

15. Data reconciliation failures.

Do not log complete sensitive email bodies, OAuth tokens, or unnecessary financial details.

# 26. Testing Strategy

Use four primary test layers.

## 26.1 Unit tests

Test domain logic without networks or databases where possible.

Examples:

1. Approval state transitions.

2. IPS rules.

3. Portfolio calculations.

4. Date logic.

5. Relevance scoring rules.

6. Provenance creation.

7. Model escalation policy.

## 26.2 Integration tests

Test:

1. PostgreSQL repositories.

2. Redis queue behavior.

3. OAuth token storage.

4. Provider adapters against recorded fixtures.

5. Alembic migrations.

6. Ollama structured output behavior.

## 26.3 Contract tests

Test normalized provider interfaces against actual or sandbox provider responses where permitted.

A provider adapter should fail visibly when an external schema changes.

## 26.4 End to end tests

Test full user workflows such as:

1. Ask for today’s calendar.

2. Retrieve current Schwab positions.

3. Create a calendar proposal.

4. Approve and execute a calendar proposal using a test calendar.

5. Draft an email proposal.

6. Verify that no action occurs before approval.

7. Modify a proposal and verify that prior approval is invalidated.

Use fake external adapters for most automated end to end tests.

Use separate controlled live verification scripts for real external systems.

# 27. Documentation Requirements

Create and maintain:

```text
README.md
ARCHITECTURE.md
CONSTITUTION.md
SECURITY.md
DATA_MODEL.md
APPROVAL_MODEL.md
MODEL_ROUTING.md
INTEGRATIONS.md
TESTING.md
OPERATIONS.md
ROADMAP.md
DECISION_LOG.md
GLOSSARY.md
CONTRIBUTING.md
```

## 27.1 README

The README should explain:

1. What Echo is.

2. Current capabilities.

3. What Echo deliberately cannot do.

4. How to run the system.

5. How to run tests.

6. Repository map.

7. Current phase.

8. Where architecture decisions are documented.

## 27.2 Architecture decision records

Use numbered architecture decision records for material decisions.

Each record should include:

1. Context.

2. Decision.

3. Alternatives considered.

4. Consequences.

5. Reversal conditions.

Examples:

```text
docs/decisions/ADR_0001_modular_monolith.md
docs/decisions/ADR_0002_postgresql_system_of_record.md
docs/decisions/ADR_0003_centralized_approval_engine.md
docs/decisions/ADR_0004_local_and_hosted_model_routing.md
```

## 27.3 Decision log

The decision log should provide an accessible chronological index of important product and engineering decisions.

Do not allow design reasoning to survive only inside chat history.

# 28. Development Workflow

For every phase:

1. Restate the phase objective.

2. Inspect relevant existing files.

3. Identify architectural impact.

4. List files to create or modify.

5. Implement the smallest complete vertical slice.

6. Add tests.

7. Run formatting.

8. Run linting.

9. Run type checking.

10. Run architecture checks.

11. Run tests.

12. Run security checks where relevant.

13. Update documentation.

14. Summarize results.

15. Record unresolved risks.

16. Stop before beginning the next phase.

Do not perform unrelated cleanup during a feature phase.

Do not combine multiple major phases into one implementation pass.

Do not claim completion unless verification commands actually pass.

When a command fails, show the failure, diagnose it, and fix it before proceeding.

# 29. Sequential Implementation Roadmap

## Phase 0: Repository constitution and architectural freeze

Objective:

Create the governing documents before implementation.

Deliverables:

1. Product constitution.

2. Architecture map.

3. Repository structure.

4. Dependency rules.

5. Coding standards.

6. File and function size rules.

7. Approval model.

8. Provenance model.

9. Security principles.

10. Model routing principles.

11. Testing strategy.

12. Initial architecture decision records.

Verification:

1. Every top level directory has documented ownership.

2. Every major dependency direction is documented.

3. Approval states and transitions are defined.

4. Local model and Claude responsibilities are explicit.

5. No feature code exists beyond minimal scaffolding.

Stop condition:

Do not proceed until the documents are mutually consistent.

## Phase 1: Docker development foundation

Objective:

Create a reproducible local environment.

Containers:

1. Frontend.

2. Backend.

3. Worker.

4. Scheduler.

5. PostgreSQL.

6. Redis.

7. Ollama.

Deliverables:

1. Docker Compose configuration.

2. Dockerfiles.

3. Internal networks.

4. Persistent development volumes.

5. Health checks.

6. Environment configuration template.

7. Secret handling conventions.

8. One command startup.

Verification:

1. All containers start.

2. Health checks pass.

3. Backend can reach PostgreSQL and Redis.

4. Worker can consume a test job.

5. Backend can reach Ollama.

6. Internal databases are not publicly exposed.

7. Restarting containers preserves intended state.

## Phase 2: Quality enforcement and continuous integration

Objective:

Make disorder mechanically difficult.

Deliverables:

1. Formatter.

2. Linter.

3. Type checker.

4. Unit test runner.

5. Coverage reporting.

6. Function length check.

7. File length check.

8. Complexity check.

9. Import boundary check.

10. Dependency vulnerability scan.

11. Secret scan.

12. Continuous integration workflow.

Verification:

1. A deliberate forbidden import fails the architecture test.

2. A deliberate function over 500 lines fails the build.

3. A deliberate type error fails the build.

4. A deliberate test failure blocks continuous integration.

## Phase 3: Core runtime contracts

Objective:

Create stable primitives used by all future domains.

Implement:

1. Configuration.

2. Clock abstraction.

3. Identifier generation.

4. Common errors.

5. Structured logging.

6. Correlation context.

7. Provenance records.

8. Event envelope.

9. Job envelope.

10. Capability definition.

11. Permission classification.

12. Read and write classification.

Verification:

1. All contracts are typed.

2. Schemas can be serialized and versioned.

3. Test clock supports deterministic tests.

4. Provenance records can represent source and calculation lineage.

## Phase 4: Database and repository foundation

Objective:

Establish Neon serverless Postgres as the durable system of record.

Implement:

1. Database session management.

2. Migration framework.

3. Base tables.

4. Repository interfaces.

5. Transaction boundaries.

6. Audit event storage.

7. Job records.

8. Source records.

9. Model call records.

10. Tool call records.

Verification:

1. Migrations apply to an empty database.

2. Migrations can be recreated in continuous integration.

3. Repository tests pass against real PostgreSQL.

4. Transaction rollback behavior is verified.

5. Sensitive values are not logged.

## Phase 5: Capability registry and tool execution

Objective:

Build a general capability system rather than keyword specific integration logic.

Implement:

1. Capability registry.

2. Input validation.

3. Output validation.

4. Permission checks.

5. Timeout handling.

6. Tool call audit records.

7. Error normalization.

8. Read capability execution.

9. Fake test capabilities.

Verification:

1. Invalid inputs never reach providers.

2. A capability cannot run without required permission.

3. Tool calls are auditable.

4. Provider specific data does not leak across domain boundaries.

5. The orchestration layer can discover capabilities without keyword lists.

## Phase 6: Central approval engine

Objective:

Complete the approval architecture before any real write integration.

Implement:

1. Proposal model.

2. Proposal state machine.

3. Payload hashing.

4. Validation.

5. Expiration.

6. Approval recording.

7. Rejection.

8. Editing workflow.

9. Execution authorization.

10. Idempotency.

11. Verification result handling.

12. Audit records.

Use a fake external write adapter.

Verification:

1. Execution without approval fails.

2. Self approval by the assistant is impossible.

3. Approval binds to exact payload.

4. Editing invalidates approval.

5. Expired approval fails.

6. Duplicate execution is prevented.

7. Failed external verification produces the correct state.

This phase is a hard prerequisite for all real write capabilities.

## Phase 7: Model gateway

Objective:

Create replaceable Claude and Ollama adapters.

Implement:

1. Common model request schema.

2. Common model response schema.

3. Claude adapter.

4. Ollama adapter.

5. Structured output validation.

6. Retry policy.

7. Timeout policy.

8. Token and latency tracking.

9. Cost estimation for hosted calls.

10. Task classification.

11. Escalation policy.

12. Prompt template ownership.

Verification:

1. The application can switch providers through configuration.

2. Provider SDK objects remain inside adapters.

3. Invalid structured local output is rejected.

4. Escalation rules are tested.

5. Model calls cannot directly execute external actions.

## Phase 8: Minimal conversation vertical slice

Objective:

Create a real conversation using the shared capability system.

Implement:

1. Conversation records.

2. Message records.

3. Streaming response API.

4. Conversation orchestration.

5. Current time read capability.

6. Provenance display.

7. Model selection.

8. Basic frontend chat.

Verification:

1. The user can ask for the current date and time.

2. The system calls the clock capability.

3. The response includes actual current time.

4. The model does not assume time from session context.

5. Conversation history persists.

6. Restarting containers does not erase conversation data.

## Phase 9: Memory foundation

Objective:

Add controlled persistent memory.

Implement:

1. Memory types.

2. Memory candidate extraction using Ollama.

3. Durable memory records.

4. Confirmation state.

5. Supersession.

6. Expiration.

7. Retrieval ranking.

8. Memory audit trail.

9. User memory view.

10. Memory deletion.

Verification:

1. Extracted candidates are not automatically treated as confirmed facts.

2. Conflicting memories are detectable.

3. Deleted memory no longer appears in retrieval.

4. Source context remains traceable.

## Phase 10: Google Calendar read integration

Objective:

Read the real schedule reliably.

Implement:

1. Google OAuth.

2. Minimal read scopes.

3. Token refresh.

4. Calendar listing.

5. Event search.

6. Event detail retrieval.

7. Recurring event normalization.

8. Free and busy lookup.

9. Calendar cache.

10. Freshness handling.

11. Calendar capability definitions.

Verification:

1. Real calendar events can be retrieved.

2. Recurring instances are correctly represented.

3. Timezones are correct.

4. Expired tokens recover correctly.

5. Read failures are surfaced honestly.

6. No write scope is requested.

## Phase 11: Calendar approval gated writes

Objective:

Add narrow, safe calendar modifications.

Implement in order:

1. Create event proposal.

2. Create event execution.

3. Post execution verification.

4. Modify event proposal.

5. Modify event execution.

6. Delete event proposal.

7. Delete event execution.

8. Recurring scope controls.

Verification:

1. No event changes before approval.

2. Full event payload appears in review.

3. Duplicate event creation is prevented.

4. External result is reloaded and verified.

5. Recurring event scope is explicit.

## Phase 12: Schwab read integration

Objective:

Create a verified portfolio source of truth.

Implement:

1. Schwab OAuth.

2. Read only scopes.

3. Account discovery.

4. Account number protection.

5. Balance retrieval.

6. Position retrieval.

7. Quote retrieval.

8. Historical price retrieval where supported.

9. Raw response storage policy.

10. Normalization.

11. Immutable snapshots.

12. Reconciliation.

13. Freshness policy.

Verification:

1. Account totals reconcile to Schwab data.

2. Position market values reconcile.

3. Missing fields remain missing rather than estimated.

4. Partial API responses produce visible warnings.

5. No trading endpoint is implemented.

6. Real account identifiers are masked in user facing displays and logs.

## Phase 13: Portfolio calculations and dashboard

Objective:

Turn verified Schwab data into useful deterministic analysis.

Implement:

1. Total account value.

2. Position weights.

3. Cross account exposure.

4. Asset class mapping.

5. Sector mapping.

6. Concentration analysis.

7. Unrealized gain and loss where cost basis exists.

8. Data freshness.

9. Calculation provenance.

10. Money dashboard.

Verification:

1. Every displayed number traces to snapshot records.

2. Arithmetic is covered by unit tests.

3. Rounding rules are documented.

4. Missing cost basis does not produce fake gain calculations.

5. Dashboard clearly shows last verified sync time.

## Phase 14: IPS system

Objective:

Create written, versioned strategy constraints.

Implement:

1. IPS schema.

2. IPS editor.

3. Versioning.

4. Account assignment.

5. Allocation ranges.

6. Concentration rules.

7. Restricted securities.

8. Rule evaluation.

9. Compliance results.

10. Drift dashboard.

Verification:

1. IPS rules are deterministic.

2. Rule breaches cite both the IPS version and portfolio snapshot.

3. Updating an IPS does not rewrite historical evaluations.

4. Echo flags drift but does not trade.

## Phase 15: Financial data provider evaluation harness

Objective:

Evaluate external research providers through live tests rather than marketing claims.

Do not select a permanent provider before this phase.

Build a provider evaluation harness that measures:

1. Authentication success.

2. Actual free access.

3. Rate limits observed.

4. Historical depth.

5. Symbol coverage.

6. Data freshness.

7. Field completeness.

8. Documentation quality.

9. Reliability.

10. Licensing constraints.

11. Response latency.

12. Schema stability.

13. Cost after free limits.

Evaluate separate needs:

1. Fundamentals.

2. Earnings.

3. Analyst ratings.

4. Company news.

5. SEC filings.

6. Form 4 transactions.

7. Congressional disclosures.

8. Market history not already supplied by Schwab.

Produce a dated provider decision report with live test evidence.

Do not trust a provider’s statement that a free tier exists unless an actual request succeeds under the intended account and use case.

## Phase 16: Research ingestion foundation

Objective:

Build provider independent research storage.

Implement:

1. Security master.

2. Issuer identity.

3. Source ingestion.

4. Raw source records.

5. Normalized records.

6. Deduplication.

7. Entity resolution.

8. Freshness.

9. Evidence package generation.

10. Provider fallback rules.

Verification:

1. Two providers can map into the same domain schema.

2. Source conflicts remain visible.

3. Provider replacement does not alter domain interfaces.

4. Every normalized item retains source lineage.

## Phase 17: News intelligence

Objective:

Surface a small amount of materially relevant news.

Implement:

1. News ingestion.

2. Source quality policy.

3. Entity matching.

4. Duplicate clustering.

5. Event type classification through Ollama.

6. Relevance scoring.

7. Portfolio and thesis matching.

8. Local summarization.

9. Claude synthesis of selected stories.

10. User feedback signals.

Verification:

1. Duplicate stories collapse.

2. Low relevance trending stories are suppressed.

3. Material portfolio news outranks generic popularity.

4. The final narrative links back to evidence.

5. The local model cannot silently invent facts.

## Phase 18: SEC Form 4 pipeline

Objective:

Build insider transaction intelligence.

Implement:

1. SEC source retrieval.

2. Filing parsing.

3. Insider identity normalization.

4. Transaction type normalization.

5. Ownership change.

6. Historical insider profile.

7. Deterministic anomaly features.

8. Local filing context classification.

9. Evidence view.

10. Claude interpretation when requested.

Verification:

1. Grants and open market purchases are distinguished.

2. Planned sales are identified when data supports it.

3. Transaction values and ownership changes are computed in code.

4. Anomaly claims explain the comparison baseline.

5. Echo avoids unsupported accusations.

## Phase 19: Congressional disclosure pipeline

Objective:

Build careful political transaction analysis.

Implement:

1. Disclosure ingestion.

2. Politician identity.

3. Committee assignment history.

4. Asset identity.

5. Transaction ranges.

6. Filing delay.

7. Sector classification.

8. Historical trade profiles.

9. Committee relationship features.

10. Evidence based anomaly candidates.

Verification:

1. Transaction ranges are not converted into false exact amounts.

2. Committee membership uses the membership effective at the relevant date.

3. Correlation is not described as proof of misconduct.

4. Every relationship can be inspected.

## Phase 20: Gmail read integration

Objective:

Read and organize the inbox.

Implement:

1. Gmail OAuth.

2. Minimal read scopes.

3. Search.

4. Message retrieval.

5. Thread retrieval.

6. Attachment metadata.

7. Safe attachment handling.

8. Email cache.

9. Local classification.

10. Action item extraction.

11. Response needed detection.

12. Inbox dashboard.

Verification:

1. Thread order is correct.

2. Message metadata is preserved.

3. Local summaries cite source messages.

4. Sensitive content is not unnecessarily sent to Claude.

5. No send or modification scope is requested.

## Phase 21: Gmail approval gated writes

Objective:

Add safe email actions.

Implement in order:

1. Draft proposal.

2. Create draft execution.

3. Update draft proposal.

4. Update draft execution.

5. Send proposal.

6. Send execution.

7. Reply proposal.

8. Reply execution.

9. Archive proposal.

10. Label proposal.

11. Trash proposal.

Verification:

1. The complete message is shown before sending.

2. Recipients and attachments are explicit.

3. An edit invalidates approval.

4. Duplicate send is prevented.

5. Sent state is externally verified.

## Phase 22: Unified dashboard

Objective:

Create the first cohesive personal operating view.

Implement:

1. Today.

2. Money.

3. Attention.

4. Projects.

5. Conversation.

6. Integration status.

7. Approval inbox.

8. Freshness indicators.

9. Responsive design.

10. Accessibility.

Verification:

1. Dashboard values come from backend APIs.

2. Every card shows freshness or status.

3. Approval actions cannot be mistaken for ordinary buttons.

4. No business logic exists only in the frontend.

5. Chat can access the same capabilities as dashboard actions.

## Phase 23: Project and task intelligence

Objective:

Add durable project state without pretending to replace a full project management platform.

Implement:

1. Projects.

2. Goals.

3. Milestones.

4. Tasks.

5. Decisions.

6. Blockers.

7. Status updates.

8. Relevant document links.

9. Memory integration.

10. Dashboard summary.

Verification:

1. Project status is based on stored facts.

2. Decisions are historically traceable.

3. The assistant distinguishes proposed tasks from committed tasks.

4. Task modifications use approval if they affect an external system.

## Phase 24: Proactive monitoring foundation

Objective:

Enable controlled background evaluations without autonomous consequential action.

Implement:

1. Monitor definitions.

2. Trigger schedules.

3. Condition evaluation.

4. Deduplication.

5. Quiet hours.

6. Notification preferences.

7. Alert state.

8. Alert acknowledgement.

9. Alert suppression.

10. Evaluation audit.

Initial monitor examples:

1. Calendar conflict.

2. Stale Schwab sync.

3. IPS concentration breach.

4. Material portfolio news.

5. Important unanswered email.

6. Integration failure.

Verification:

1. Monitors may notify but cannot execute consequential actions.

2. Duplicate alerts are suppressed.

3. Every alert shows why it triggered.

4. Users can disable a monitor.

## Phase 25: Evaluation and trust dashboard

Objective:

Measure whether Echo is actually becoming reliable.

Track:

1. Tool accuracy.

2. Calculation reconciliation.

3. Data freshness.

4. Local model schema success.

5. Local model classification quality.

6. Claude escalation rate.

7. Hallucination incidents.

8. Approval bypass attempts blocked.

9. Execution verification rate.

10. Integration uptime.

11. User corrections.

12. Cost.

13. Latency.

Create regression datasets from corrected failures.

Do not rely only on general language model benchmarks. Evaluate Echo on Echo’s actual workflows.

## Phase 26: Voice preparation

Objective:

Prepare interfaces for voice without allowing voice logic to diverge from chat.

Implement:

1. Input channel abstraction.

2. Streaming transcript events.

3. Response chunk events.

4. Interruption handling contract.

5. Voice safe approval requirement.

6. Spoken summary versus full readable review distinction.

No consequential action may be approved solely through an ambiguous voice command. High risk actions require an explicit readable confirmation interface.

## Phase 27: Paper trading observation

Objective:

Evaluate trade reasoning without enabling trading.

Implement only after portfolio, research, IPS, provenance, approvals, and monitoring are mature.

Capabilities:

1. Create hypothetical trade proposals.

2. Record rationale.

3. Record expected outcome.

4. Track hypothetical performance.

5. Compare against no action.

6. Measure thesis quality.

7. Measure timing.

8. Review failures.

No order endpoint should exist.

## Phase 28: Future narrow trade execution

This phase is not authorized by this prompt.

Do not implement live trading.

It may be considered only after a separate architecture review, security review, legal and operational review, extended paper tracking, explicit user authorization, and creation of tighter approval controls.

# 30. Phase Completion Report Format

At the end of each phase, provide:

```text
Phase:
Objective:
Status:

Files created:
Files modified:

Architecture decisions:
Implementation summary:
Tests added:
Commands run:
Verification results:
Known limitations:
Security considerations:
Documentation updated:
Unresolved risks:
Recommended next phase:
```

Do not begin the recommended next phase until explicitly instructed.

# 31. Implementation Behavior Rules

1. Never conceal failing tests.

2. Never claim a provider works without a successful test.

3. Never create mock data and present it as real.

4. Clearly label fake, fixture, sandbox, and production data.

5. Do not silently change architectural contracts.

6. Record material deviations in an architecture decision record.

7. Avoid speculative abstractions.

8. Avoid feature specific hacks inside shared orchestration.

9. Prefer explicit names over cleverness.

10. Prefer smaller modules over giant files.

11. Prefer typed schemas over arbitrary dictionaries.

12. Prefer deterministic policy code over prompt instructions.

13. Prefer provider adapters over vendor logic inside domains.

14. Prefer vertical slices over broad incomplete scaffolding.

15. Prefer one reliable capability over five unstable capabilities.

16. Never add write permissions during a read integration phase.

17. Never bypass the approval engine for convenience.

18. Never expose a capability in one interface only.

19. Never perform authoritative financial arithmetic in a language model.

20. Stop when a phase is complete.

# 32. Immediate Assignment

Begin with Phase 0 only.

Do not write application feature code.

Perform the following:

1. Propose the final repository structure.

2. Draft the governing architecture documents.

3. Define module ownership.

4. Define dependency rules.

5. Define the approval state machine.

6. Define the provenance model.

7. Define the model routing policy.

8. Define function and file size enforcement.

9. Define the initial database domains conceptually without implementing migrations.

10. Create the first architecture decision records.

11. Identify contradictions or unresolved risks in this specification.

12. Recommend precise resolutions.

13. Present the Phase 0 completion report.

Do not proceed to Phase 1 until explicitly instructed.
