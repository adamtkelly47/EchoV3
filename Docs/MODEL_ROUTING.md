Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Model Routing Policy

## Purpose

This document defines the model gateway contract and the deterministic policy that routes work between Ollama (local), Claude (hosted), and deterministic code. See ADR_0004 for the decision this document elaborates.

## Model Gateway

A single gateway (`providers/models/`) exposes one common request/response schema to the rest of the application. Claude and Ollama are adapters behind it. No application or domain code calls the Claude SDK or an Ollama client directly — CONSTITUTION.md's Model Independence and Provider SDK Leakage rules apply to models exactly as they apply to any other provider.

**Implemented in Phase 7.** `providers/models/contracts.py` (`ModelRequest`/`ModelResponse`/`TaskType`/`Provider`), `providers/models/claude/adapter.py` (real `anthropic` SDK calls; unit-tested against a mocked client — no live Claude API key exists in the dev environment, so live verification is a documented gap, see `DECISION_LOG.md`), `providers/models/ollama/adapter.py` (real HTTP calls to Ollama's REST API; **live-tested** against the running `ollama` container with a small pulled model, `smollm2:135m`), `providers/models/escalation.py` (deterministic policy), `providers/models/gateway.py` (`ModelGateway` — provider selection via `core.config.Settings.default_model_provider`, structured-output validation via `generate_structured()`). Claude per-token pricing (`providers/models/claude/pricing.py`) was verified against anthropic.com on 2026-07-21, not assumed — see the module's own docstring for the note on Sonnet 5's introductory price expiring 2026-08-31.

Common request schema includes: task type, prompt/context payload, required output schema (when structured output is expected), timeout, retry policy, and a routing hint (not a routing decision — see below).

Common response schema includes: output (raw or schema-validated), token usage, latency, provider identity, cost estimate (for hosted calls), and validation status.

## Deterministic Code Workloads (never a model)

Per PROMPT.md Section 12.3, the following are always deterministic code, never Ollama or Claude:

Arithmetic; portfolio calculations; date/time calculations; threshold evaluations; IPS rule checks; duplicate detection when exact identifiers exist; schema validation; permission enforcement; approval state transitions; audit records; account reconciliation; data freshness checks; rate limiting; retry behavior; security rules; source ranking rules that can be explicitly encoded.

A model may explain a result that deterministic code produced. It may never produce the authoritative result itself (Constitution: Deterministic Computation).

## Ollama Default Workloads

Per PROMPT.md Section 12.1: parsing raw text into a defined schema, categorizing news, scoring likely relevance, extracting entities, converting API responses into normalized candidate records, summarizing batches of articles, grouping duplicate stories, extracting claims from documents, identifying possible anomalies for deterministic review, producing compact context packages for Claude, classifying emails, drafting low-risk first-pass summaries, memory candidate extraction, document chunk labeling, historical transaction feature generation, bulk watchlist screening.

Ollama output is always treated as **candidate analysis**, not verified truth. It is schema-validated on every call, and, where the downstream use is consequential, checked against deterministic rules before being trusted.

## Claude Workloads

Per PROMPT.md Section 12.2: direct user conversation, cross-domain synthesis, complicated investment-thesis evaluation, reasoned pushback, planning, decision support, interpreting conflicting evidence, producing final research narratives, determining what information is missing, handling novel user requests, high-quality drafting when wording matters, and deciding whether local model output is sufficient or requires escalation.

## Escalation Policy

Escalation from Ollama to Claude is decided by deterministic policy code, not by prompt wording (Constitution: Prompt Philosophy — "If changing a prompt changes deterministic business behavior, the architecture is incorrect"). The policy considers:

1. Task type.
2. Stakes (does this affect a consequential recommendation?).
3. Ambiguity of the request.
4. Required reasoning depth.
5. Data sensitivity.
6. Token volume.
7. Local model's reported confidence.
8. Whether structured output validation succeeded on the local pass.
9. Cost budget remaining.
10. Explicit user preference.

A task escalates to Claude when any of the following holds (PROMPT.md Section 12.4):

- Required schema validation repeatedly fails on the local model.
- The task involves material judgment.
- Evidence conflicts.
- The local model expresses low confidence.
- The task affects a consequential recommendation.
- The user is directly conversing and expects a polished response.
- The local output would expose the user to meaningful financial, legal, reputational, or operational risk.

This policy is implementation in `domains/capabilities` policy code (or a dedicated routing policy module once Phase 7 begins), covered by unit tests before any domain depends on it (ADR_0004).

## What the Capability Planner May and May Not Do With Models

A language model (via the Capability Planner stage, REQUEST_LIFECYCLE.md) may propose which registered capabilities to use. It may not register capabilities, authorize capabilities, execute capabilities directly, or choose its own model provider — those are deterministic application decisions (Constitution: Capability Planner section).

## Cost and Quality Tracking

From Phase 7 onward, the gateway records per-call latency, token usage, hosted cost estimate, local processing volume, and escalation rate, so that "local is cheaper" remains a measured fact rather than an assumption (PROMPT.md Section 12.4, closing note; Section 25 Observability).

## Replaceability

Both adapters implement the same gateway interface. Replacing Claude with another hosted model, or Ollama with another local inference server, is a provider-layer change only — domain and application code is unaffected (Constitution: Provider Independence; PROMPT.md Section 3.7).
