"""PROMPT.md Phase 24: proactive monitoring foundation. Monitoring/alerting
lives in the System domain (Docs/DOMAIN_OWNERSHIP.md's System Domain: owns
"System Alerts", "platform monitoring", "raise alert"/"acknowledge alert")
— there is no separate "Monitoring" domain in the 13-domain catalog.
"""

from __future__ import annotations

from enum import Enum


class MonitorType(str, Enum):
    """PROMPT.md Phase 24's own "initial monitor examples" list, minus
    "important unanswered email" — Email/Gmail integration is deferred
    (Docs/DECISION_LOG.md's Phases 20-21 entry), so that monitor type is
    deliberately not included rather than defined and left permanently
    unevaluable."""

    CALENDAR_CONFLICT = "calendar_conflict"
    STALE_SCHWAB_SYNC = "stale_schwab_sync"
    IPS_CONCENTRATION_BREACH = "ips_concentration_breach"
    MATERIAL_PORTFOLIO_NEWS = "material_portfolio_news"
    INTEGRATION_FAILURE = "integration_failure"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertStatus(str, Enum):
    """PROMPT.md Phase 24 implement items 8-9: acknowledgement and
    suppression are distinct, real terminal states — not one generic
    "dismissed" flag. `ACTIVE` is the only state a monitor sweep may ever
    create; a human (or, for suppression, the dedup/mute policy) is what
    moves an alert out of it."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"
