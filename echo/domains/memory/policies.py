"""Policies decide; they never persist data (CONSTITUTION.md: Policy) — same
convention as domains/approvals/policies.py.
"""

from __future__ import annotations

from datetime import datetime

from domains.memory.models import ACTIVE_STATUSES, VALID_TRANSITIONS, MemoryStatus
from domains.memory.schemas import MemoryRecord


def is_valid_transition(current: MemoryStatus, target: MemoryStatus) -> bool:
    return target in VALID_TRANSITIONS[current]


def clamp_confidence(confidence: float) -> float:
    """CONSTITUTION.md: Memory Confidence — "Confidence shall never be
    binary" — bounded to [0.0, 1.0] rather than trusting the caller (a model
    extraction result) to have stayed in range."""
    return max(0.0, min(1.0, confidence))


def is_expired(record: MemoryRecord, now: datetime) -> bool:
    return record.expires_at is not None and now >= record.expires_at


def is_active(record: MemoryRecord, now: datetime) -> bool:
    """The only records retrieval/ranking ever returns: CONFIRMED and not
    past their own expiry. A record whose status is still CONFIRMED but
    whose expires_at has lapsed is not active even before the expiration
    sweep persists the EXPIRED transition (PROMPT.md Phase 9 verification:
    expired/deleted memory must not appear in retrieval)."""
    return record.status in ACTIVE_STATUSES and not is_expired(record, now)


def conflicts_with(existing: MemoryRecord, subject_key: str, content: str) -> bool:
    """Two memories conflict when they claim to be the durable answer for
    the same subject but disagree on the fact itself (CONSTITUTION.md:
    Memory Lifecycle — conflicting evidence is a first-class case, not
    silently overwritten). Only an active record can conflict — a
    superseded/expired/deleted one is history, not a live disagreement."""
    return (
        existing.status in ACTIVE_STATUSES
        and existing.subject_key == subject_key
        and existing.content != content
    )


def rank_score(record: MemoryRecord, query_terms: frozenset[str], now: datetime) -> float:
    """Deterministic retrieval ranking (PROMPT.md Phase 9 implement item 7):
    keyword overlap between the query and the memory's content, weighted by
    confidence, with a small recency tie-breaker. DOMAIN_OWNERSHIP.md notes
    embedding services/vector databases are an implementation detail Memory
    doesn't own — this keyword-based score is a real, testable ranking
    policy that doesn't require standing up that infrastructure before any
    consuming domain actually needs semantic search."""
    content_terms = frozenset(record.content.lower().split())
    overlap = len(query_terms & content_terms)
    recency_bonus = 0.0
    if record.confirmed_at is not None:
        age_days = max((now - record.confirmed_at).total_seconds() / 86400, 0.0)
        recency_bonus = 1.0 / (1.0 + age_days)
    return overlap * record.confidence + 0.01 * recency_bonus
