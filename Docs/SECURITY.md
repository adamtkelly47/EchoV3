Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Security Principles

## Purpose

This document states Echo's security requirements at the architecture level, per PROMPT.md Section 23 and CONSTITUTION.md's Security Philosophy ("Security is architectural. Not procedural."). It defines principles binding on every future phase; it does not describe implementation, since no integrations exist yet at Phase 0.

## Least Privilege

Every OAuth integration requests the minimum scope required for its current phase. Read integrations (Calendar Phase 10, Schwab Phase 12, Gmail Phase 20) request read-only scopes; write scopes are never requested until the corresponding write phase (Phase 11, none for Schwab in v1, Phase 21) is reached and the Approval Engine (Phase 6) already exists. Future permissions are never requested preemptively (Constitution: Least Privilege).

## Secrets

Secrets (OAuth tokens, API keys, database credentials) never appear in source code, tests, documentation, sample configuration, or logs. They are stored in secure secret management (`infrastructure/secrets/`) and encrypted at rest. Development and production credentials are kept separate. Access tokens are never committed to source control.

## Data Handling

- Sensitive payloads (full email bodies, account numbers, unredacted financial detail) are redacted before being sent to a model unless the specific task requires them.
- Real account identifiers are masked in user-facing displays and logs (explicit requirement of Phase 12's verification criteria).
- Complete sensitive email bodies, OAuth tokens, and unnecessary financial detail are never written to logs (Section 25).
- Data retention policy is defined per domain as write capabilities are added; it is not retrofitted.

## Session and Web Security

- Secure cookies (or equivalent) for session handling.
- CSRF protection on state-changing endpoints.
- Redirect target validation on OAuth callback flows.
- Rate limiting on sensitive endpoints (auth, approval actions, write capabilities).
- Reauthentication or stronger confirmation required for future high-risk actions (e.g. anything above `risk_level: medium` in APPROVAL_MODEL.md).

## Network Isolation

Ollama, PostgreSQL, and Redis are never exposed publicly. Private service-to-service communication routes through an internal Docker network (Phase 1 verification criterion: "Internal databases are not publicly exposed").

## Dependency and Code Security

- Dependencies are scanned for known vulnerabilities and pinned to specific versions (Phase 2 deliverable: dependency vulnerability scan).
- Static security scanning (e.g. Bandit, Semgrep — see TESTING.md) runs in CI.
- Secret scanning runs in CI to catch accidental credential commits before merge.

## Authentication vs. Authorization

Authentication establishes identity; authorization establishes permission. These are separate responsibilities (Constitution). Authentication is owned by Identity, in cooperation with external identity providers (Google, Microsoft, Apple — see DOMAIN_OWNERSHIP.md's Provider Mapping). Authorization (permission checks) is deterministic code, never a language model decision — this is a Constitutional invariant, not a preference (Constitution: Authorization; PROMPT.md Section 3.2 corollary).

## Operational Continuity

- PostgreSQL is backed up, and restoration is tested (Section 23 item 17-18) — this begins once Phase 4 introduces the database, not before.
- An incident response document is maintained once there is a running system to have incidents in; it will be added as `Docs/INCIDENT_RESPONSE.md` in the phase where real external credentials are first connected (Phase 10), not speculatively now.

## Applicability by Phase

Security requirements are not deferred to a "security phase" — they are binding from the phase in which the relevant surface first exists. Phase 1 (Docker foundation) must satisfy network isolation. Phase 4 (database) must satisfy secrets-at-rest and backup testability. Every OAuth-based phase (10, 12, 20) must satisfy least-privilege scoping and token handling before that phase can be marked verified.
