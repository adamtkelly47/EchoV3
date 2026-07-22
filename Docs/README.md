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

**Phase 22 — Unified dashboard.** Phases 0-19 (governing documents, Docker foundation, quality/CI, core runtime contracts, database foundation, capability registry, approval engine, model gateway, conversation loop, memory foundation, Google Calendar read/write, Schwab read integration, portfolio calculations and dashboard, IPS system, financial data provider evaluation harness, research ingestion foundation, news intelligence, SEC Form 4 insider intelligence, Congressional disclosure pipeline) are complete. Phases 20-21 (Gmail read integration and approval-gated writes) are deferred at the user's explicit request — not attempted this phase. Phase 22 builds Echo's first cohesive personal-operating-system view: a new `application/queries/dashboard_query.py` (the first population of `application/queries/`) coordinates Portfolio, Calendar, Approvals, and Conversation in one read, and a new `app/page.tsx` (replacing Phase 8's placeholder status page) renders it as seven cards — Today, Money, Attention, Approval inbox, Projects, Conversation, Integration status. Every card carries its own status/freshness (verification 2): a disconnected integration or a connected-but-never-synced one are honest, distinct states, never a failure that takes down the other cards. "Projects" is honestly `not_available` (no Projects domain exists yet — that's Phase 23), not a fabricated empty card. Approval actions (verification 3) are visually and behaviorally distinct from ordinary buttons — bordered green/red buttons with explicit `aria-label`s and a native confirmation dialog restating the real proposal summary before either fires. Live-verified end to end against the real backend: real portfolio totals for the actual connected account, a real proposed calendar-event approval appearing in and then being cleared from the real approval inbox via the real endpoints, and a real browser (Playwright, headless Chromium) screenshot-verified at both desktop and mobile viewport widths. See `Docs/DECISION_LOG.md`'s Phase 22 entry for the full design and live verification results.

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
