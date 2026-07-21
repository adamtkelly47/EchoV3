Version: 1.0
Status: APPROVED
Owner: Echo Project
Last Updated: July 2026

# ADR 0004: Deterministic Local/Hosted Model Routing

## Context

PROMPT.md Sections 5.7, 5.8, and 12 require a single model gateway with replaceable Claude and Ollama adapters, and an explicit division of labor: Ollama for bulk classification/extraction/normalization workloads, Claude for conversation/synthesis/judgment, and deterministic code for all arithmetic and rule evaluation. CONSTITUTION.md's Model Independence principle prohibits the system from assuming vendor-specific behavior, and the Capability Planner section prohibits language models from executing capabilities directly or determining their own permissions.

## Decision

All model calls route through one model gateway (`providers/models/`) using a common request/response schema, with Claude and Ollama as interchangeable adapters behind it. A deterministic task-classification and escalation policy — implemented as code, not prompt text — decides whether a task runs on Ollama or escalates to Claude, using the criteria in MODEL_ROUTING.md (task type, stakes, ambiguity, evidence conflict, local-model confidence, schema validation success, cost budget, user preference). This follows the Constitution's Prompt Philosophy: "If changing a prompt changes deterministic business behavior, the architecture is incorrect."

## Alternatives Considered

**Let the model choose its own provider or escalate itself mid-conversation.** Rejected — violates Model Independence and the Capability Planner rule that "Language models SHALL NOT... execute capabilities directly," and it makes routing behavior depend on prompt wording rather than deterministic policy.

**Single-provider-only approach (Claude for everything, or Ollama for everything).** Rejected — violates the Cost Discipline principle (Section 3.6) and Replaceability (Section 3.7); an all-Claude approach also fails the intended local-first cost profile, and an all-Ollama approach cannot meet the quality bar for direct user conversation and high-stakes synthesis.

## Consequences

- Phase 7 must ship escalation-policy unit tests before any domain depends on model routing.
- Provider SDK objects (Claude/Ollama response types) never escape `providers/models/`; domains and application code only see the common schema.
- Usage, latency, cost, and escalation-rate metrics must be tracked from Phase 7 onward so routing decisions can be evaluated against real evidence rather than assumption (Section 12.4, last paragraph).

## Reversal Conditions

If a future task category proves the deterministic escalation policy insufficient or miscalibrated, it is amended via a new ADR with updated criteria — never by embedding ad hoc judgment calls into prompts.
