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

**Phase 14 — IPS system.** Phases 0-13 (governing documents, Docker foundation, quality/CI, core runtime contracts, database foundation, capability registry, approval engine, model gateway, conversation loop, memory foundation, Google Calendar read/write, Schwab read integration, portfolio calculations and dashboard) are complete. Phase 14 adds a written, versioned Investment Policy Statement (IPS) — allocation ranges, a concentration rule, restricted securities, optional account scoping — and deterministic compliance evaluation, all inside the existing `domains/portfolio/` module (no new domain; DOMAIN_OWNERSHIP.md already assigns IPS ownership to Portfolio). IPS versions are immutable once written: editing one never rewrites its rules, it supersedes it with a new active version, so a `ComplianceResult` citing an old `ips_version_id` always reflects exactly what that version said, forever. Phase 13's hardcoded 10% concentration default is now superseded automatically by an active IPS's own threshold — verified live, the dashboard's concentration warnings visibly changed the moment a real IPS was created. Verified live against the real connected Schwab account: a real IPS produced 4 real compliance breaches (an allocation-range breach, a concentration breach on `UNH`, and two restricted-security breaches on `SMCI` held across both accounts), and a second IPS version correctly superseded the first without altering its stored rules. See `Docs/DECISION_LOG.md`'s Phase 14 entry for the full versioning and evaluation design, and its Phase 13 entry for the dashboard/sector scoping decisions this phase builds on.

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
