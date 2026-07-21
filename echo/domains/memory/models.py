"""The memory lifecycle state machine (CONSTITUTION.md: Memory Lifecycle —
"Observation -> Candidate -> Review -> Promotion -> Usage -> Supersession ->
Archive"). Invalid transitions are rejected in code, not merely discouraged
by convention, matching the Approvals precedent (domains/approvals/models.py).
"""

from __future__ import annotations

from enum import Enum


class MemoryStatus(str, Enum):
    # "Candidate" in CONSTITUTION.md's lifecycle diagram — extracted but not
    # yet reviewed. Never treated as a confirmed fact (CONSTITUTION.md:
    # "Promotion into durable memory should remain conservative").
    CANDIDATE = "candidate"
    # "Promotion"/"Usage" — a reviewed, durable fact. The only status
    # retrieval ranks over (domains/memory/policies.py: is_active).
    CONFIRMED = "confirmed"
    # "Supersession" — replaced by a newer CONFIRMED record. Terminal.
    SUPERSEDED = "superseded"
    # Reached expires_at without renewal. Terminal.
    EXPIRED = "expired"
    # Explicit user-initiated removal (DOMAIN_OWNERSHIP.md: "delete memory").
    # Terminal.
    DELETED = "deleted"


# Only CONFIRMED memories are "active" (CONSTITUTION.md's Usage stage) —
# the only status retrieval/ranking ever returns.
ACTIVE_STATUSES: frozenset[MemoryStatus] = frozenset({MemoryStatus.CONFIRMED})

VALID_TRANSITIONS: dict[MemoryStatus, frozenset[MemoryStatus]] = {
    MemoryStatus.CANDIDATE: frozenset({MemoryStatus.CONFIRMED, MemoryStatus.DELETED}),
    MemoryStatus.CONFIRMED: frozenset(
        {MemoryStatus.SUPERSEDED, MemoryStatus.EXPIRED, MemoryStatus.DELETED}
    ),
    MemoryStatus.SUPERSEDED: frozenset(),
    MemoryStatus.EXPIRED: frozenset(),
    MemoryStatus.DELETED: frozenset(),
}
