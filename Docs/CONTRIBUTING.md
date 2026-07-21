Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Contributing / Phase Workflow

## Purpose

This document is the operating procedure every implementation phase follows, per PROMPT.md Sections 28, 30, and 31, and CONSTITUTION.md's Phase Discipline. It applies to human contributors and to AI-assisted implementation sessions equally.

## Per-Phase Workflow

For every phase, in order:

1. Restate the phase objective.
2. Inspect relevant existing files.
3. Identify architectural impact — does this touch ownership, dependency direction, or any area requiring an ADR (CONSTITUTION.md's ADR trigger list)?
4. List files to create or modify.
5. Implement the smallest complete vertical slice — implementation, tests, and documentation together, not implementation now and tests later.
6. Add tests.
7. Run formatting.
8. Run linting.
9. Run type checking.
10. Run architecture checks.
11. Run tests.
12. Run security checks where relevant.
13. Update documentation.
14. Summarize results using the Phase Completion Report Format below.
15. Record unresolved risks.
16. **Stop.** Do not begin the next phase until explicitly instructed.

No unrelated cleanup during a feature phase. No combining multiple major phases into one pass. No claiming completion unless verification commands actually passed — show the failure, diagnose it, fix it, before proceeding, if any command fails.

## Phase Completion Report Format

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

## Implementation Behavior Rules

Condensed from PROMPT.md Section 31 — these apply throughout, not just at phase boundaries:

- Never conceal failing tests.
- Never claim a provider works without a successful test.
- Never create mock data and present it as real; label fake, fixture, sandbox, and production data explicitly (CONSTITUTION.md: Environment Integrity).
- Do not silently change architectural contracts — record material deviations in an ADR.
- Avoid speculative abstractions and feature-specific hacks inside shared orchestration.
- Prefer explicit names, smaller modules, typed schemas, deterministic policy code, and provider adapters over their respective alternatives.
- Prefer vertical slices over broad incomplete scaffolding, and one reliable capability over five unstable ones.
- Never add write permissions during a read-integration phase.
- Never bypass the Approval Engine for convenience.
- Never expose a capability in only one interface.
- Never perform authoritative financial arithmetic in a language model.
- Stop when a phase is complete.

## When an ADR Is Required

Per CONSTITUTION.md, an ADR is required before implementing changes affecting: module ownership, dependency direction, provider interfaces, persistence model, approval architecture, orchestration, security model, application architecture, repository structure, capability routing, or model routing. When in doubt, write the ADR — see `Docs/decisions/` for the format (Context, Decision, Alternatives Considered, Consequences, Reversal Conditions) and ADR_0001–0005 for examples.

## Communication Style

Per PROMPT.md Section 2: technically rigorous, explicit about major architectural decisions, clear about unfamiliar concepts when they first appear, lean during ordinary build work, honest about uncertainty and limitations, and resistant to unnecessary complexity. Push back when a requested shortcut would damage correctness, safety, maintainability, or long-term architecture — do not implement it silently and do not implement it just because it was asked for.
