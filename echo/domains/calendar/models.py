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
