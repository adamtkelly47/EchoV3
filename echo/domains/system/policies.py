"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as every other domain's own
policies.py. Every monitor-condition function here takes already-fetched
real domain data (a list of `CalendarEvent`, a `ComplianceResult`, ...) and
returns a pure, deterministic verdict — the actual fetching happens in
`application/orchestrators/monitoring.py`, which is the one place allowed
to call into another domain's service (CONSTITUTION.md dependency
direction: domains/ never import another domain).
"""

from __future__ import annotations

from datetime import datetime

from domains.system.schemas import MonitorDefinition


def find_calendar_conflicts(
    events: list[tuple[str, datetime, datetime]],
) -> list[tuple[str, str]]:
    """PROMPT.md Phase 24's "calendar conflict" monitor. Takes plain
    `(event_id, start, end)` tuples rather than `domains.calendar.schemas.
    CalendarEvent` directly — `domains/system/` must never import another
    domain's schemas (CONSTITUTION.md dependency direction,
    scripts/check_architecture.py's `no-domain-to-domain-imports` rule);
    `application/orchestrators/monitoring.py` does that translation, the
    same "speaks in primitives" pattern providers use at the domain
    boundary. Two events conflict when their time ranges overlap at all —
    back-to-back events (one's end equals the other's start) are not a
    conflict."""
    conflicts: list[tuple[str, str]] = []
    for i, (id_a, start_a, end_a) in enumerate(events):
        for id_b, start_b, end_b in events[i + 1 :]:
            if start_a < end_b and start_b < end_a:
                first, second = sorted((id_a, id_b))
                conflicts.append((first, second))
    return conflicts


def is_within_quiet_hours(monitor: MonitorDefinition, now: datetime) -> bool:
    """PROMPT.md Phase 24 implement item 5: "quiet hours." Both bounds are
    plain UTC hour-of-day integers; a window that wraps past midnight
    (e.g. 22 -> 7) is handled explicitly rather than silently broken."""
    start, end = monitor.quiet_hours_start_utc, monitor.quiet_hours_end_utc
    if start is None or end is None:
        return False
    hour = now.hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def calendar_conflict_dedup_key(event_id_a: str, event_id_b: str) -> str:
    """Order-independent — the same pair of conflicting events always
    produces the same key regardless of which one is discovered first."""
    first, second = sorted((event_id_a, event_id_b))
    return f"calendar_conflict:{first}:{second}"


def stale_schwab_sync_dedup_key(user_id: str, now: datetime) -> str:
    """Deduplicated per calendar day (UTC) — a sync that's been stale for
    three days should not re-alert every evaluation sweep within that same
    day (PROMPT.md Phase 24 verification 2: "duplicate alerts are
    suppressed"), but a new day's sweep is a genuinely new fact worth
    re-surfacing if still unresolved."""
    return f"stale_schwab_sync:{user_id}:{now.date().isoformat()}"


def ips_concentration_breach_dedup_key(user_id: str, rule_type: str, description: str) -> str:
    return f"ips_concentration_breach:{user_id}:{rule_type}:{description}"


def material_portfolio_news_dedup_key(user_id: str, digest_id: str) -> str:
    return f"material_portfolio_news:{user_id}:{digest_id}"


def integration_failure_dedup_key(user_id: str, provider_name: str, now: datetime) -> str:
    return f"integration_failure:{user_id}:{provider_name}:{now.date().isoformat()}"
