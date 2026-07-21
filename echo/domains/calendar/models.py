"""Calendar's own vocabulary, kept independent of any single provider's raw
strings — Google's `status`/`transparency` fields are translated into these
by domains/calendar/policies.py, so a future Outlook/Apple/ICS provider
(Docs/DOMAIN_OWNERSHIP.md: Calendar's other listed external providers)
would translate into the same enum rather than Calendar depending on
Google-specific values throughout.
"""

from __future__ import annotations

from enum import Enum


class EventStatus(str, Enum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class RecurringEditScope(str, Enum):
    """PROMPT.md Phase 11 implement item 8 ("recurring scope controls") /
    verification item 5 ("recurring event scope is explicit"). Exactly the
    two scopes Google's API natively supports (verified live against
    developers.google.com/calendar/api/guides/recurringevents) — a caller
    must say which one explicitly; there is no silent default. "This and
    following" is not offered: Google's own guide describes it as a 2-call
    workaround (truncate the series, insert a new one), not a native scope,
    and a partially-completable 2-call operation isn't "narrow, safe."""

    SINGLE_INSTANCE = "single_instance"
    ENTIRE_SERIES = "entire_series"
