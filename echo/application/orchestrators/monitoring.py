"""PROMPT.md Phase 24: proactive monitoring foundation. Coordinates System
(monitor/alert lifecycle) with Portfolio, Calendar, and Research (the real
domains each monitor type's condition is evaluated against) — exactly the
cross-domain coordination CONSTITUTION.md reserves for the Application
layer, matching `NewsIntelligenceOrchestrator`'s own precedent for reading
a second domain.

Every `_evaluate_*` method only ever *reads* from Portfolio/Calendar/
Research and *writes* an `Alert` via `SystemService` — it never calls an
approval, a calendar write, or any other consequential action.
Structurally, not just by convention, this is what makes PROMPT.md Phase 24
verification 1 ("monitors may notify but cannot execute consequential
actions") true: this module has no dependency on `ApprovalService` or any
domain's write-adapter/orchestrator, so there is nothing here *capable* of
executing a consequential action even if a bug tried to.

"Important unanswered email" (one of PROMPT.md's own "initial monitor
examples") is not implemented — Email/Gmail integration is deferred
(Docs/DECISION_LOG.md's Phases 20-21 entry) — matching `MonitorType`'s own
documented omission.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from core.errors import EchoError
from core.time import Clock
from domains.calendar.service import CalendarService
from domains.portfolio.service import PortfolioService
from domains.research.service import ResearchService
from domains.system.models import MonitorType
from domains.system.policies import (
    calendar_conflict_dedup_key,
    find_calendar_conflicts,
    integration_failure_dedup_key,
    ips_concentration_breach_dedup_key,
    is_within_quiet_hours,
    material_portfolio_news_dedup_key,
    stale_schwab_sync_dedup_key,
)
from domains.system.schemas import EvaluationRun, MonitorDefinition
from domains.system.service import SystemService
from infrastructure.database.repositories.audit import AuditRepository


class MonitoringEvaluateInput(BaseModel):
    """The `core.jobs.JobEnvelope` input for the `monitoring.evaluate` job
    type `apps/scheduler/main.py` enqueues and `apps/worker/main.py`
    consumes. Empty on purpose — this phase's sweep evaluates every
    enabled monitor across every user with one on record in a single pass;
    there is no per-job parameter yet (PROMPT.md Phase 24 implement item
    2: "trigger schedules")."""


_INTEGRATION_FAILURE_LOOKBACK = timedelta(hours=24)
_CALENDAR_CONFLICT_LOOKAHEAD = timedelta(days=2)

# (real audit action, human-readable provider name) — both real actions
# recorded since Phases 10-12, long before any monitoring concept existed.
_INTEGRATION_FAILURE_ACTIONS = (
    ("calendar.token_refresh_failed", "Google Calendar"),
    ("schwab.token_refresh_failed", "Schwab"),
)


class MonitoringOrchestrator:
    def __init__(
        self,
        system: SystemService,
        portfolio: PortfolioService,
        calendar: CalendarService,
        research: ResearchService,
        audit: AuditRepository,
        clock: Clock,
    ) -> None:
        self._system = system
        self._portfolio = portfolio
        self._calendar = calendar
        self._research = research
        self._audit = audit
        self._clock = clock

    async def evaluate_all_enabled_monitors(self) -> list[EvaluationRun]:
        """The scheduled sweep's single entry point (`apps/worker/main.py`'s
        `monitoring.evaluate` job type)."""
        monitors = await self._system.list_all_enabled_monitors()
        return [await self._evaluate_one(monitor) for monitor in monitors]

    async def _evaluate_one(self, monitor: MonitorDefinition) -> EvaluationRun:
        now = self._clock.now_utc()
        quiet = is_within_quiet_hours(monitor, now)
        evaluator = {
            MonitorType.CALENDAR_CONFLICT: self._evaluate_calendar_conflict,
            MonitorType.STALE_SCHWAB_SYNC: self._evaluate_stale_schwab_sync,
            MonitorType.IPS_CONCENTRATION_BREACH: self._evaluate_ips_concentration_breach,
            MonitorType.MATERIAL_PORTFOLIO_NEWS: self._evaluate_material_portfolio_news,
            MonitorType.INTEGRATION_FAILURE: self._evaluate_integration_failure,
        }[monitor.monitor_type]
        try:
            triggered, detail = await evaluator(monitor, now, quiet)
        except EchoError as exc:
            triggered, detail = False, f"evaluation error: {exc}"
        return await self._system.record_evaluation_run(monitor, triggered=triggered, detail=detail)

    async def _evaluate_calendar_conflict(
        self, monitor: MonitorDefinition, now: datetime, quiet: bool
    ) -> tuple[bool, str]:
        if not await self._calendar.is_connected(monitor.user_id):
            return False, "Google Calendar not connected"
        events = await self._calendar.list_events(
            monitor.user_id,
            calendar_id="primary",
            time_min=now,
            time_max=now + _CALENDAR_CONFLICT_LOOKAHEAD,
        )
        primitives = [(e.event_id, e.start, e.end) for e in events if not e.all_day]
        conflicts = find_calendar_conflicts(primitives)
        summaries = {e.event_id: e.summary for e in events}
        for event_id_a, event_id_b in conflicts:
            summary_a = summaries.get(event_id_a, event_id_a)
            summary_b = summaries.get(event_id_b, event_id_b)
            await self._system.raise_alert(
                monitor,
                message=f'"{summary_a}" overlaps with "{summary_b}"',
                reason=(
                    f'"{summary_a}" and "{summary_b}" have overlapping time ranges in the '
                    "next 2 days"
                ),
                severity="medium",
                dedup_key=calendar_conflict_dedup_key(event_id_a, event_id_b),
                created_during_quiet_hours=quiet,
            )
        return (
            bool(conflicts),
            f"{len(conflicts)} conflict(s) among {len(events)} upcoming event(s)",
        )

    async def _evaluate_stale_schwab_sync(
        self, monitor: MonitorDefinition, now: datetime, quiet: bool
    ) -> tuple[bool, str]:
        if not await self._portfolio.is_connected(monitor.user_id):
            return False, "Schwab not connected"
        try:
            dashboard = await self._portfolio.get_dashboard(monitor.user_id)
        except EchoError:
            return False, "no synced portfolio snapshot yet"
        if not dashboard.is_stale:
            return False, f"last verified sync at {dashboard.last_verified_sync_at.isoformat()}"
        await self._system.raise_alert(
            monitor,
            message="Portfolio sync is stale",
            reason=f"last verified sync at {dashboard.last_verified_sync_at.isoformat()}",
            severity="low",
            dedup_key=stale_schwab_sync_dedup_key(monitor.user_id, now),
            created_during_quiet_hours=quiet,
        )
        return True, f"stale since {dashboard.last_verified_sync_at.isoformat()}"

    async def _evaluate_ips_concentration_breach(
        self, monitor: MonitorDefinition, now: datetime, quiet: bool
    ) -> tuple[bool, str]:
        if not await self._portfolio.is_connected(monitor.user_id):
            return False, "Schwab not connected"
        compliance = await self._portfolio.get_latest_compliance_result(monitor.user_id)
        if compliance is None or compliance.compliant:
            return False, "no active IPS breach on record"
        for breach in compliance.breaches:
            await self._system.raise_alert(
                monitor,
                message="IPS compliance breach",
                reason=breach.description,
                severity="high",
                dedup_key=ips_concentration_breach_dedup_key(
                    monitor.user_id, breach.rule_type, breach.description
                ),
                created_during_quiet_hours=quiet,
            )
        return True, f"{len(compliance.breaches)} breach(es) on the latest compliance result"

    async def _evaluate_material_portfolio_news(
        self, monitor: MonitorDefinition, now: datetime, quiet: bool
    ) -> tuple[bool, str]:
        if not await self._portfolio.is_connected(monitor.user_id):
            return False, "Schwab not connected"
        try:
            dashboard = await self._portfolio.get_dashboard(monitor.user_id)
        except EchoError:
            return False, "no synced portfolio snapshot yet"
        digests_found = 0
        for weight in dashboard.position_weights:
            issuer = await self._research.get_issuer_by_ticker(weight.symbol)
            if issuer is None:
                continue
            try:
                digest = await self._research.get_latest_digest(issuer.issuer_id)
            except EchoError:
                continue
            digests_found += 1
            await self._system.raise_alert(
                monitor,
                message=f"New material news for a held position: {weight.symbol}",
                reason=digest.narrative,
                severity="medium",
                dedup_key=material_portfolio_news_dedup_key(monitor.user_id, digest.digest_id),
                created_during_quiet_hours=quiet,
            )
        return (
            digests_found > 0,
            f"{digests_found} held position(s) had a news digest on record "
            f"out of {len(dashboard.position_weights)}",
        )

    async def _evaluate_integration_failure(
        self, monitor: MonitorDefinition, now: datetime, quiet: bool
    ) -> tuple[bool, str]:
        """No Identity domain scopes audit events by user, so this check is
        platform-wide — an honest reflection of this being a single-user
        system in practice (this codebase's own established convention),
        not a real multi-tenant gap."""
        since = now - _INTEGRATION_FAILURE_LOOKBACK
        triggered = False
        details = []
        for action, provider_name in _INTEGRATION_FAILURE_ACTIONS:
            failures = await self._audit.list_recent_by_action(action, since, result="failure")
            if failures:
                triggered = True
                await self._system.raise_alert(
                    monitor,
                    message=f"{provider_name} integration is failing",
                    reason=(
                        f"{len(failures)} token refresh failure(s) recorded in the last "
                        f"{_INTEGRATION_FAILURE_LOOKBACK.days * 24}h"
                    ),
                    severity="high",
                    dedup_key=integration_failure_dedup_key(monitor.user_id, provider_name, now),
                    created_during_quiet_hours=quiet,
                )
                details.append(f"{provider_name}: {len(failures)} failure(s)")
        return triggered, "; ".join(details) if details else "no integration failures recorded"
