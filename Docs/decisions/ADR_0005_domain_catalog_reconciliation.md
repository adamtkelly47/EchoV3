Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0005: Domain Catalog Reconciliation

## Context

PROMPT.md Section 7 proposes a repository tree containing `domains/{conversation, approvals, actions, integrations, portfolio, research, calendar, email, memory, documents, notifications, projects, identity}`.

DOMAIN_OWNERSHIP.md's authoritative Domain Catalog (Section "Domain Catalog") lists thirteen domains: Portfolio, Research, Calendar, Email, Memory, Conversation, Projects, Identity, Notifications, Approvals, Capabilities, Knowledge, System.

These two lists disagree. PROMPT.md's tree includes `actions`, `integrations`, and `documents`, none of which appear in the catalog. The catalog includes `Capabilities`, `Knowledge`, and `System`, none of which appear in PROMPT.md's tree.

CONSTITUTION.md states that DOMAIN_OWNERSHIP.md is "constitutionally binding" and is "the authoritative definition of ownership." The Single Owner Principle and Bounded Context Principle require this ambiguity to be resolved before any domain directories are created.

## Decision

DOMAIN_OWNERSHIP.md's thirteen-domain catalog is authoritative. The repository tree in ARCHITECTURE.md supersedes PROMPT.md Section 7 as follows:

1. **`integrations/` is removed as a domain.** Vendor/integration logic belongs under `providers/`, which already exists in the proposed tree. This follows directly from the Provider Principle ("Providers never own business concepts") and the Provider Mapping table in DOMAIN_OWNERSHIP.md, which assigns every external provider to an owning domain. Integration *status* (connected accounts, provider configuration, sync health) is owned by Identity (Connected Accounts, Provider Configuration) and System (Runtime Status, Feature Availability) — not by a standalone domain.

2. **`actions/` is removed as a standalone domain.** Consequential execution is owned by Approvals under its "Execution Ownership" responsibility (CONSTITUTION.md: "Consequential execution is owned by the Approval Engine. Individual domains SHALL NOT implement independent execution flows."). Execution logic lives inside `domains/approvals/` as an internal collaborator (e.g. an `execution` submodule), not a separate top-level domain, because it does not currently meet any of the Domain Split Criteria in DOMAIN_OWNERSHIP.md (no independent lifecycle, no unrelated business rules, no ambiguous ownership, no scaling requirement, no separate team).

3. **`documents/` is removed as a standalone domain.** General reference/document material is owned by Knowledge (Reference Documents, Knowledge Articles). Research-specific documents (filings, research reports) remain owned by Research, which already lists Research Reports and Company Filings among its owned concepts. No document concept is left ownerless.

4. **`capabilities/`, `knowledge/`, and `system/` are added** to the `domains/` directory to match the catalog.

## Alternatives Considered

**Expand DOMAIN_OWNERSHIP.md to add Actions, Integrations, and Documents as new domains.** Rejected. Integrations directly contradicts Provider Independence (CONSTITUTION.md: "Domain behavior shall never depend directly upon provider SDKs... Any provider may be replaced. Domain behavior shall remain unchanged" — the inverse also holds: a domain must not exist solely to wrap providers). Actions and Documents do not satisfy the Domain Expansion Rules (owns a distinct business capability, owns authoritative state, owns unique business rules, owns an independent lifecycle) independent of Approvals and Knowledge respectively.

**Leave the two documents inconsistent and resolve ownership ad hoc during implementation.** Rejected. CONSTITUTION.md requires ownership to be unambiguous before implementation begins; runtime discovery of ownership is an explicitly listed anti-pattern.

## Consequences

- PROMPT.md Section 7's tree is superseded by ARCHITECTURE.md's tree for this repository.
- `providers/` must reflect the full Provider Mapping table from DOMAIN_OWNERSHIP.md.
- When Phase 6 (Central Approval Engine) is implemented, `domains/approvals/` will need an execution-focused internal module (proposal lifecycle vs. execution pipeline) rather than a sibling domain.
- Phase 16 (Research ingestion) and any future knowledge-base work must place general reference content under `domains/knowledge/`, not a new `documents/` domain.

## Reversal Conditions

If execution logic inside Approvals grows to exhibit an independent lifecycle, unrelated business rules, ambiguous ownership, or a genuine scaling/deployment requirement distinct from approval-decision logic, a new ADR may split it into its own domain, per the Domain Split Criteria in DOMAIN_OWNERSHIP.md. The same applies to Integrations or Documents if a future capability set demonstrably cannot be owned by Identity/System or Knowledge/Research respectively.
