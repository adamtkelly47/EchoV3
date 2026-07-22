Version: 1.0
Status: DRAFT
Owner: Echo Project
Last Updated: July 2026

# Instructions: How to Use Echo

This is a practical, task-oriented guide to everything built across Phases 0-27. It assumes the system is already built (see `Docs/README.md` and `Docs/DECISION_LOG.md` for *why* things are built the way they are — this document is about *how to actually use them*).

For governing rules, read `Docs/CONSTITUTION.md` first. This file never overrides it.

## 1. Running the system

### First-time setup

1. Copy `.env.example` to `.env` at the repo root and fill in real values. At minimum you need:
   - `DATABASE_URL` — a Neon Postgres connection string (pooled endpoint recommended). Use a dedicated dev branch, never production.
   - `SECRET_ENCRYPTION_KEY` — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Required before any OAuth flow (Calendar, Schwab) will work — tokens are encrypted at rest with it.
   - Everything else in `.env.example` is optional and gates a specific feature (see the table below). Leave a block blank and that feature degrades honestly (e.g. `not_connected` on a dashboard card) rather than crashing.

2. Bring the stack up:
   ```bash
   docker compose up -d
   ```
   This starts `backend` (FastAPI, port 8000), `frontend` (Next.js, port 3000), `worker`, `scheduler`, `redis`, and `ollama`. Postgres itself is Neon (cloud), not a container.

3. Apply migrations (first run, or after pulling new phases):
   ```bash
   docker exec echo-backend-1 alembic upgrade head
   ```

4. Confirm health:
   ```bash
   curl http://localhost:8000/health              # liveness only
   curl http://localhost:8000/health/dependencies # real DB/Redis/Ollama checks
   ```

### What gates which feature

| Env var | Unlocks |
|---|---|
| `ANTHROPIC_API_KEY` | Claude escalation calls (interpretation steps in Research; conversation still works Ollama-only without it) |
| `GOOGLE_OAUTH_CLIENT_ID`/`SECRET` | Calendar read/write |
| `SCHWAB_CLIENT_ID`/`SECRET` | Portfolio sync, dashboard, IPS, quotes, paper trading |
| `FINNHUB_API_KEY` | Company news, fundamentals |
| `RESEARCH_CONTACT_EMAIL` | SEC EDGAR (Form 4 insider filings) and Senate eFD (PTR disclosures) — both are keyless but require a real contact email for fair-access compliance |

Gmail (`Docs/PROMPT.md` Phases 20-21) is a **standing deferral** at the user's explicit request — no code exists for it, and no env var unlocks it.

### Rebuilding after code or dependency changes

The three backend services (`backend`, `worker`, `scheduler`) build from the same Dockerfile and image context (`./echo`), but each is a separate running container. A `docker cp` into one does not update the others, and none of them carry `tests/`, `scripts/`, or dev dependencies (`pyproject.toml`'s `[dev]` extra) in their production image — those only exist if manually installed into a container's writable layer, which a rebuild discards. If you change backend code:
```bash
docker compose build backend worker scheduler
docker compose up -d backend worker scheduler
```
This is not optional if you added a new dependency — an image that was never rebuilt will `ModuleNotFoundError` on the new import the moment the worker or scheduler tries to use it (this happened for real in Phase 24 when `cryptography` was added in Phase 10/12 but the worker/scheduler images were never rebuilt to match).

## 2. The domain map

Echo is a modular monolith (`Docs/decisions/ADR_0001`) organized as 13 canonical business domains (`Docs/DOMAIN_OWNERSHIP.md`), each with its own API prefix. Not all 13 are populated in code yet — only the ones a phase actually needed (No Future Scaffolding).

| Domain | API prefix | Populated | Owns |
|---|---|---|---|
| Conversation | `/conversations` | Phase 8, extended Phase 26 | Chat sessions, messages, channel (text/voice), streaming |
| Memory | `/memory` | Phase 9 | Candidate/confirmed facts, corrections, supersession |
| Calendar | `/calendar` | Phase 10-11 | Google Calendar read/write (write is approval-gated) |
| Portfolio | `/portfolio` | Phase 12-14, extended Phase 27 | Schwab accounts/positions, dashboard, IPS compliance, paper trading |
| Research | `/research` | Phase 16-19 | Issuers, news digests, Form 4 insider filings, Senate PTR disclosures |
| Approvals | `/approvals` | Phase 6, extended Phase 26 | The shared consequential-action gate every domain write goes through |
| Projects | `/projects` | Phase 23 | Goals, milestones, tasks, decisions, blockers, status updates |
| System | `/monitors`, `/trust` | Phase 24-25 | Background monitors/alerts, evaluation/trust metrics, hallucination incidents |
| Dashboard (cross-domain read) | `/dashboard` | Phase 22 | Unified one-screen view |
| Email, Identity, Notifications, Capabilities, Knowledge | — | Not populated | Gmail deferred; the rest have no phase that needed them yet |

Capabilities exists in code as an internal registry (`domains/capabilities/`) with no direct API surface of its own — it's what `Conversation`'s planner calls into.

## 3. Core workflows

### 3.1 Chat (text and voice)

```bash
# Start a session
curl -X POST http://localhost:8000/conversations -H "Content-Type: application/json" \
  -d '{"user_id": "me"}'
# -> {"session_id": "conv_...", "started_at": "..."}

# Send a message (non-streaming)
curl -X POST http://localhost:8000/conversations/{session_id}/messages \
  -H "Content-Type: application/json" -d '{"content": "What time is it?", "channel": "text"}'

# Send a message and stream the reply (NDJSON — one ResponseChunkEvent per line)
curl -N -X POST http://localhost:8000/conversations/{session_id}/messages/stream \
  -H "Content-Type: application/json" -d '{"content": "Tell me a joke", "channel": "voice"}'

# Read history
curl "http://localhost:8000/conversations/{session_id}/messages"
```

`channel` is `"text"` or `"voice"` — it's recorded on every message but doesn't change what happens (Phase 26's whole point: chat and a future voice frontend share one pipeline). Streaming responses are newline-delimited JSON; each line has `text`, `is_final`, and `interrupted`. If the HTTP client disconnects mid-stream, the server detects it and marks the partial message `interrupted=true` — there's no separate "stop" call needed.

There is no speech-to-text or text-to-speech integration in this codebase. `handle_transcript_stream` (the orchestrator method a real voice frontend would call with partial STT chunks) exists and is tested, but has no HTTP endpoint yet — wiring a real STT/WebSocket transport is future work.

### 3.2 Memory

```bash
# Extract a candidate fact from free text (uses the model gateway)
curl -X POST http://localhost:8000/memory/extract -H "Content-Type: application/json" \
  -d '{"user_id": "me", "text": "My favorite color is blue.", "source_type": "conversation", "source_id": "conv_1"}'

# Confirm it (candidates are never auto-confirmed)
curl -X POST http://localhost:8000/memory/{memory_id}/confirm

# Correct it later (must be confirmed first — supersede replaces it with a new record)
curl -X POST http://localhost:8000/memory/{memory_id}/supersede -H "Content-Type: application/json" \
  -d '{"content": "My favorite color is green.", "confidence": 0.95, "source_type": "user_correction", "source_id": "{memory_id}"}'
```

To have a correction counted by the trust dashboard (below) as a genuine "user correction" rather than a routine system-driven supersession, use `POST /trust/corrections/{memory_id}` instead of calling `/memory/{id}/supersede` directly — it's the one unambiguous entry point (`TrustOrchestrator`) and also seeds a regression case.

### 3.3 Google Calendar

```bash
# 1. Connect (one-time OAuth)
curl "http://localhost:8000/calendar/oauth/authorize?user_id=me"   # open the returned URL, approve, get redirected back automatically

# 2. Read
curl "http://localhost:8000/calendar/events?user_id=me&time_min=...&time_max=..."

# 3. Propose a write (never executes directly — every write is a proposal)
curl -X POST http://localhost:8000/calendar/events -H "Content-Type: application/json" \
  -d '{"user_id": "me", "summary": "Team sync", "start": "...", "end": "..."}'
# -> returns a ProposalResponse with a proposal_id, status "awaiting_approval"

# 4. Approve it through the shared Approval Engine (see 3.6 below)
curl -X POST http://localhost:8000/approvals/{proposal_id}/approve -H "Content-Type: application/json" \
  -d '{"approving_user_id": "me", "confirmation_method": "readable"}'

# 5. Execute (only possible once approved)
curl -X POST http://localhost:8000/calendar/proposals/{proposal_id}/execute
```
Modify/delete events follow the same propose → approve → execute pattern.

### 3.4 Schwab portfolio

```bash
# 1. Connect
curl "http://localhost:8000/portfolio/schwab/oauth/authorize?user_id=me"
# Schwab's callback URL is never actually reachable — after approving, paste
# the resulting dead-page URL (or just the code param), plus the state value
# from the original authorize redirect, into:
curl -X POST http://localhost:8000/portfolio/schwab/oauth/complete -H "Content-Type: application/json" \
  -d '{"state": "<state from step 1>", "redirect_value": "<pasted value>"}'

# 2. Sync (pulls real accounts/positions/balances, reconciles, snapshots)
curl -X POST "http://localhost:8000/portfolio/sync?user_id=me"

# 3. Read the computed dashboard (never triggers a live call itself — reads the last snapshot)
curl "http://localhost:8000/portfolio/dashboard?user_id=me"

# 4. Set an Investment Policy Statement and evaluate compliance drift
curl -X POST http://localhost:8000/portfolio/ips -H "Content-Type: application/json" -d '{ ... }'
curl -X POST "http://localhost:8000/portfolio/ips/compliance/evaluate?user_id=me"
```
**There is no order or trade-execution endpoint anywhere in this codebase.** Schwab's OAuth token is technically trade-capable (Schwab has no separate read-only product), but nothing here ever calls a trading endpoint with it — verified by inspecting the running backend's own `/openapi.json` in Phase 27.

### 3.5 Paper trading (evaluate reasoning, never execute)

```bash
# Propose a hypothetical trade — hypothetical_price is a real, just-fetched quote
curl -X POST http://localhost:8000/portfolio/hypothetical-trades -H "Content-Type: application/json" \
  -d '{"user_id": "me", "symbol": "AAPL", "action": "buy", "quantity": 10, "rationale": "Strong earnings expected", "expected_outcome": "Price rises 5% in 30 days", "expected_horizon_days": 30, "rationale_references": ["thesis_123"]}'

# Record a performance observation whenever you want to check on it (on-demand, not automatic)
curl -X POST http://localhost:8000/portfolio/hypothetical-trades/{trade_id}/samples

# See the full evaluation: gain/loss, comparison against doing nothing, thesis direction, timing
curl "http://localhost:8000/portfolio/hypothetical-trades/{trade_id}"

# Close it with a human-authored review — terminal, one-time
curl -X POST http://localhost:8000/portfolio/hypothetical-trades/{trade_id}/close -H "Content-Type: application/json" \
  -d '{"review_note": "Thesis played out within 12 days"}'
```

### 3.6 Approvals (the shared gate)

Every consequential write in this system — Calendar, and any future domain — goes through the same lifecycle: `propose → submit_for_approval → approve/reject → execute → verify`. There is no way around it (`Docs/CONSTITUTION.md`: Approval Principle — "There shall be no exceptions").

```bash
curl "http://localhost:8000/approvals/{proposal_id}"                  # full readable review (every field)
curl "http://localhost:8000/approvals/{proposal_id}/spoken-summary"   # short, TTS-appropriate preview only
curl -X POST http://localhost:8000/approvals/{proposal_id}/approve -H "Content-Type: application/json" \
  -d '{"approving_user_id": "me", "confirmation_method": "readable"}'
curl -X POST http://localhost:8000/approvals/{proposal_id}/reject
```
`confirmation_method` is `"readable"` (default) or `"voice"`. **A `HIGH`-risk proposal can never be approved with `"voice"` alone** — the service raises a real `403 voice_confirmation_not_allowed_for_high_risk`. `LOW`/`MEDIUM`-risk proposals can be voice-approved. The system can never approve its own proposal (`SelfApprovalNotAllowedError`), and any material edit to a proposal after approval invalidates it (payload hash mismatch).

### 3.7 Research (news, insider filings, Congressional trades)

```bash
# Sync an issuer's identity/security master
curl -X POST "http://localhost:8000/research/issuers/sync?ticker=AAPL"

# Generate a news digest (cites sources, never a bare claim)
curl -X POST "http://localhost:8000/research/issuers/{issuer_id}/news/digest?ticker=AAPL&company_name=Apple+Inc&user_id=me"

# Ingest and classify Form 4 insider transactions (SEC EDGAR)
curl -X POST "http://localhost:8000/research/issuers/{issuer_id}/insiders/ingest?cik=..."
curl "http://localhost:8000/research/issuers/{issuer_id}/insiders/{insider_cik}/evidence"
# Opt-in Claude interpretation of a footnote (never automatic):
curl -X POST "http://localhost:8000/research/issuers/{issuer_id}/insiders/{insider_cik}/interpret?company_name=..."

# Congressional (Senate) trade disclosures
curl -X POST "http://localhost:8000/research/politicians/ingest?start_date=2026-01-01&limit=50"
curl "http://localhost:8000/research/politicians/{bioguide_id}/evidence"
```

### 3.8 Projects

Full CRUD + lifecycle under `/projects` — goals, milestones, tasks (with a real, code-enforced state machine: `PROPOSED → COMMITTED → IN_PROGRESS → DONE`, never skipping `COMMITTED`), decisions (immutable, and each one is also recorded as a linked Memory candidate), blockers, and status updates. See the route list in section 5, or `apps/api/routes/projects.py` directly — the naming is self-explanatory (`POST /projects/{id}/goals`, `POST /projects/tasks/{id}/commit`, etc.).

### 3.9 Monitoring (background alerts)

```bash
# Register a monitor for yourself
curl -X POST http://localhost:8000/monitors -H "Content-Type: application/json" \
  -d '{"user_id": "me", "monitor_type": "calendar_conflict"}'
# monitor_type is one of: calendar_conflict, stale_schwab_sync,
# ips_concentration_breach, material_portfolio_news, integration_failure

# Trigger a sweep on demand (the real path is automatic — see section 4)
curl -X POST http://localhost:8000/monitors/evaluate

# See what fired
curl "http://localhost:8000/monitors/alerts?user_id=me"
curl -X POST http://localhost:8000/monitors/alerts/{alert_id}/acknowledge
curl -X POST http://localhost:8000/monitors/alerts/{alert_id}/suppress
```
Duplicate alerts are suppressed automatically (same `dedup_key` while still active) — you will not get spammed by the same unresolved condition every sweep. Monitors can notify but structurally cannot execute anything — the orchestrator behind them has no dependency on the Approval Engine at all.

### 3.10 Trust dashboard (is Echo actually reliable?)

```bash
curl "http://localhost:8000/trust/dashboard?user_id=me"
```
Returns 13 metrics computed from real, already-recorded signals: tool accuracy, calculation reconciliation, data freshness, local-model schema success, classification quality, Claude escalation rate, hallucination incidents, approval bypass attempts blocked, execution verification rate, integration uptime, user corrections, cost, and latency — over a 7-day window by default.

```bash
# Report a hallucination (always human-triggered — no automatic detector exists)
curl -X POST http://localhost:8000/trust/hallucination-incidents -H "Content-Type: application/json" \
  -d '{"user_id": "me", "description": "Claimed the meeting was rescheduled when it was not"}'

# Resolve it — this automatically seeds a regression case
curl -X POST http://localhost:8000/trust/hallucination-incidents/{incident_id}/resolve -H "Content-Type: application/json" \
  -d '{"resolution_note": "The meeting was not rescheduled"}'

curl "http://localhost:8000/trust/regression-cases"
```

### 3.11 Unified dashboard

```bash
curl "http://localhost:8000/dashboard?user_id=me"
```
One call, seven cards: Today (calendar), Money (portfolio), Attention (pending approvals + IPS breaches), Approval inbox, Projects, Conversation (recent sessions), Integration status. Every card carries its own `status`/`as_of` — a disconnected integration never takes down the other cards. The frontend at `http://localhost:3000/` renders this same endpoint.

## 4. What runs automatically (no action needed)

`scheduler` enqueues a `monitoring.evaluate` job to Redis every 300 seconds; `worker` consumes it and runs every enabled monitor for every user with at least one. This is the real path — `POST /monitors/evaluate` (section 3.9) is the on-demand/manual equivalent used for testing.

## 5. Full endpoint reference

Grouped by router (all under `http://localhost:8000`):

- **`/conversations`** — start, send message, stream message, get history
- **`/memory`** — extract, confirm, supersede, delete, conflicts, search, list
- **`/calendar`** — oauth authorize/callback, calendars, events (read/create/modify/delete), freebusy, proposal execute
- **`/approvals`** — get proposal, spoken-summary, approve, reject
- **`/portfolio`** — schwab oauth, sync, accounts, snapshot, dashboard, quotes, price-history, IPS (create/active/versions/compliance), hypothetical-trades (propose/list/get-evaluation/sample/close)
- **`/research`** — issuers sync/get, news digest/articles/feedback, insiders ingest/evidence/interpret, politicians ingest/evidence
- **`/dashboard`** — the unified read
- **`/projects`** — projects, goals, milestones, tasks, decisions, blockers, status-updates
- **`/monitors`** — create, list, enable/disable, evaluations, evaluate-now, alerts (list/acknowledge/suppress)
- **`/trust`** — dashboard, hallucination-incidents (report/list/resolve), corrections, regression-cases

Every route returns a typed JSON error body on failure: `{"error_code": "...", "message": "...", "correlation_id": "..."}`, with an HTTP status matching the specific error (never a bare 500 for a known domain condition).

## 6. Development workflow

```bash
# Format, lint, type-check (run inside the backend container — dev deps aren't in the prod image)
docker exec echo-backend-1 pip install -e ".[dev]"   # first time after a rebuild only
docker exec echo-backend-1 ruff format .
docker exec echo-backend-1 ruff check .
docker exec echo-backend-1 mypy .

# Architecture and size-discipline checks
docker exec echo-backend-1 python scripts/check_architecture.py
docker exec echo-backend-1 python scripts/check_size_limits.py

# Tests (copy tests/ into the container first if it was freshly rebuilt)
docker exec echo-backend-1 python -m pytest tests/unit tests/architecture -q
docker exec echo-backend-1 python -m pytest tests/integration -q   # hits real Neon — slower (~2 min)

# Migrations
docker exec echo-backend-1 alembic revision --autogenerate -m "description"
docker exec echo-backend-1 alembic upgrade head
docker exec echo-backend-1 alembic downgrade -1   # always test reversibility before trusting a new migration
```

Security/dependency scans used throughout this project's own development (not required to run the app, only to extend it safely): `vulture` (dead code), `bandit` (security), `pip-audit` (dependency vulnerabilities).

## 7. What's deliberately not here

- **Gmail integration** (`Docs/PROMPT.md` Phases 20-21) — a standing deferral at the user's explicit request, not an oversight. No code, no env var, nothing partially built.
- **Real trade execution** (`Docs/PROMPT.md` Phase 28, "Future narrow trade execution") — explicitly not authorized by PROMPT.md itself. No order endpoint exists anywhere, for real or hypothetical trades.
- **Speech-to-text / text-to-speech** — Phase 26 built the *contract* (channel abstraction, streaming events, interruption handling) a voice frontend would need, but no actual audio transport or STT/TTS vendor is integrated.
- **Automatic hallucination detection** — every hallucination incident starts from a human noticing and reporting one; there is no code anywhere that judges its own output as false or unsupported.

For the full rationale behind every design choice summarized above, `Docs/DECISION_LOG.md` has one dated entry per phase — that is the authoritative "why," this file is only the "how."
