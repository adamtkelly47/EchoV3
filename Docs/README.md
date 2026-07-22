Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Echo

## What Echo Is

Echo is a private personal AI operating system — a conversational assistant, decision-support platform, research platform, orchestration platform, memory system, and planning partner. It reads real personal data (portfolio, calendar, email, research) through authorized integrations, performs deterministic calculations in code, conducts attributable research, and proposes consequential actions for human approval. It does not autonomously execute them.

## What Echo Is Not

A generic chatbot wrapper, a collection of disconnected agents, a system where a language model invents calculations or executes writes on its own authority, a dashboard that just displays raw API data, a financial trading bot, or an autonomous decision maker. See CONSTITUTION.md's Product Definition for the full list.

## Current Phase

**Phase 23 — Project and task intelligence.** Phases 0-19 and 22 (governing documents, Docker foundation, quality/CI, core runtime contracts, database foundation, capability registry, approval engine, model gateway, conversation loop, memory foundation, Google Calendar read/write, Schwab read integration, portfolio calculations and dashboard, IPS system, financial data provider evaluation harness, research ingestion foundation, news intelligence, SEC Form 4 insider intelligence, Congressional disclosure pipeline, unified dashboard) are complete. Phases 20-21 (Gmail integration) remain deferred at the user's explicit request. Phase 23 adds a new Projects domain — the first domain in this codebase with no external providers at all (Docs/DOMAIN_OWNERSHIP.md: "third-party project management systems are providers rather than owners"). Seven real entities (Project, Goal, Milestone, Task, Decision, Blocker, StatusUpdate) give Echo durable project state without pretending to replace a project management platform. `TaskStatus` has a real, code-enforced state machine — a task is always created `PROPOSED` and cannot reach `IN_PROGRESS`/`DONE` without an explicit `COMMITTED` step first (verification 3), live-verified by watching the real API reject a premature transition with `409 invalid_task_transition`. `Decision` and `StatusUpdate` are immutable, append-only records (verification 2: "decisions are historically traceable"), and `ProjectStatusSummary` is computed fresh from these stored facts on every read (verification 1), never a free-text assertion. A new `application/orchestrators/project_memory.py` links recorded decisions into Memory as `CANDIDATE` records, never auto-confirmed (implement item 9) — live-verified end to end, including confirming the real linked memory record via the real Memory API. Phase 22's dashboard "Projects" card, previously an honest `not_available` placeholder, now shows real project/task/blocker data — live-verified with a real Playwright screenshot. See `Docs/DECISION_LOG.md`'s Phase 23 entry for the full design and live verification results.

(Per an explicit standing instruction, phases are being completed and committed continuously without waiting for a go-ahead between each — see `DECISION_LOG.md`'s 2026-07-21 entries.)

## How to Read These Docs

Start with `CONSTITUTION.md` — it is the highest authority in the repository and everything else elaborates on it, never overrides it. Then:

1. `DOMAIN_OWNERSHIP.md` — who owns what business concept (constitutionally binding).
2. `ARCHITECTURE.md` — the concrete repository structure and dependency rules.
3. `REQUEST_LIFECYCLE.md` — how a request moves through the system end to end.
4. `CAPABILITY_REGISTRY.md` — how executable behavior is registered and discovered.
5. `APPROVAL_MODEL.md` — the approval state machine gating every consequential write.
6. `DATA_MODEL.md` — conceptual state ownership and the provenance model.
7. `MODEL_ROUTING.md` — the Ollama/Claude/deterministic-code division of labor.
8. `DOMAIN_EVENTS.md` — the cross-domain event catalog.
9. `SECURITY.md` — security requirements, binding from the phase each surface first exists.
10. `TESTING.md` — the testing pyramid and mechanically enforced coding standards.
11. `CONTRIBUTING.md` — the phase workflow every implementation phase follows.
12. `decisions/ADR_000N_*.md` — the architecture decisions already made and why.
13. `DECISION_LOG.md` — chronological index of material decisions, including ones not yet worth a full ADR.
14. `OPERATIONS.md` — how to run the local environment and handle secrets.

If implementation ever appears to disagree with these documents, the documents win unless superseded by an approved ADR (CONSTITUTION.md's Constitutional Status).

## Repository Map

```text
Docs/                  # this documentation set
Docs/decisions/        # architecture decision records
echo/                  # Python: apps/api, apps/worker, apps/scheduler (shared codebase, ADR_0001)
frontend/               # Next.js/TypeScript, no business logic
docker-compose.yml
.env.example            # placeholder only — real values go in gitignored .env
```

`echo/core`, `echo/domains`, `echo/providers`, `echo/infrastructure`, `echo/api`, `echo/tests`, `echo/migrations` are defined conceptually in `ARCHITECTURE.md` and do not exist yet — they are created starting Phase 3, one vertical slice at a time.

## How to Run the System / How to Run Tests

See `OPERATIONS.md` for the one-command startup, verification steps, and secret handling conventions. There is no test suite yet — automated testing tooling is a Phase 2 deliverable.

## PROMPT.md

`PROMPT.md` is the original build specification this repository implements, organized into 29 phases. It is a source input, not itself governing documentation — where it conflicts with `CONSTITUTION.md` or `DOMAIN_OWNERSHIP.md`, those take precedence and the conflict is recorded as an ADR (see `Docs/decisions/ADR_0005_domain_catalog_reconciliation.md` for the first example).
