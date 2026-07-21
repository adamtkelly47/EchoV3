"""The Memory domain's aggregate-lifecycle owner (CONSTITUTION.md: Memory
Lifecycle). No other domain may determine what becomes durable memory
(DOMAIN_OWNERSHIP.md) — this is the only place a MemoryRecord's status
changes.
"""

from __future__ import annotations

from datetime import datetime

from core.time import Clock
from domains.memory.errors import InvalidMemoryStateTransitionError, MemoryNotFoundError
from domains.memory.models import MemoryStatus
from domains.memory.policies import clamp_confidence, conflicts_with, is_active, rank_score
from domains.memory.policies import is_valid_transition as _is_valid_transition
from domains.memory.repository import MemoryRepository
from domains.memory.schemas import MemoryRecord
from infrastructure.database.repositories.audit import AuditRepository


class MemoryService:
    def __init__(self, repository: MemoryRepository, audit: AuditRepository, clock: Clock) -> None:
        self._repository = repository
        self._audit = audit
        self._clock = clock

    async def record_candidate(
        self,
        *,
        user_id: str,
        subject_key: str,
        content: str,
        confidence: float,
        source_type: str,
        source_id: str,
        correlation_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryRecord:
        """Extraction only ever produces CANDIDATE records (PROMPT.md Phase
        9 verification: "extracted candidates are not automatically treated
        as confirmed facts") — confirming one is a separate, explicit call.
        `expires_at` is set here (rather than only at confirm time) since a
        candidate can already represent a fact known to be time-bounded."""
        record = MemoryRecord(
            user_id=user_id,
            subject_key=subject_key,
            content=content,
            status=MemoryStatus.CANDIDATE,
            confidence=clamp_confidence(confidence),
            source_type=source_type,
            source_id=source_id,
            correlation_id=correlation_id,
            created_at=self._clock.now_utc(),
            expires_at=expires_at,
        )
        await self._repository.save(record)
        await self._audit.record(
            action="memory.candidate_recorded",
            result="success",
            correlation_id=correlation_id,
            detail={"memory_id": record.memory_id, "subject_key": subject_key},
        )
        return record

    async def get(self, memory_id: str) -> MemoryRecord:
        return await self._require(memory_id)

    async def confirm(self, memory_id: str) -> MemoryRecord:
        record = await self._require(memory_id)
        confirmed = await self._transition(record, MemoryStatus.CONFIRMED)
        confirmed = confirmed.model_copy(update={"confirmed_at": self._clock.now_utc()})
        await self._repository.save(confirmed)
        conflicts = await self.detect_conflicts(confirmed)
        await self._audit.record(
            action="memory.confirmed",
            result="success",
            correlation_id=confirmed.correlation_id,
            detail={
                "memory_id": confirmed.memory_id,
                "conflict_count": len(conflicts),
                "conflicting_memory_ids": [c.memory_id for c in conflicts],
            },
        )
        return confirmed

    async def supersede(
        self,
        old_memory_id: str,
        *,
        content: str,
        confidence: float,
        source_type: str,
        source_id: str,
        correlation_id: str | None = None,
    ) -> MemoryRecord:
        """CONSTITUTION.md: Memory Lifecycle — Supersession. The old record
        is never mutated in place beyond its status (Historical Records /
        Immutability: "new records should supersede older ones")."""
        old = await self._require(old_memory_id)
        new_record = MemoryRecord(
            user_id=old.user_id,
            subject_key=old.subject_key,
            content=content,
            status=MemoryStatus.CONFIRMED,
            confidence=clamp_confidence(confidence),
            source_type=source_type,
            source_id=source_id,
            correlation_id=correlation_id,
            supersedes_memory_id=old.memory_id,
            created_at=self._clock.now_utc(),
            confirmed_at=self._clock.now_utc(),
        )
        await self._repository.save(new_record)
        await self._transition(old, MemoryStatus.SUPERSEDED)
        await self._audit.record(
            action="memory.superseded",
            result="success",
            correlation_id=correlation_id,
            detail={"old_memory_id": old.memory_id, "new_memory_id": new_record.memory_id},
        )
        return new_record

    async def delete(self, memory_id: str) -> MemoryRecord:
        record = await self._require(memory_id)
        deleted = await self._transition(record, MemoryStatus.DELETED)
        await self._audit.record(
            action="memory.deleted",
            result="success",
            correlation_id=record.correlation_id,
            detail={"memory_id": memory_id},
        )
        return deleted

    async def detect_conflicts(self, record: MemoryRecord) -> list[MemoryRecord]:
        """PROMPT.md Phase 9 verification: "conflicting memories are
        detectable." Detection only — Memory does not block or auto-resolve
        a conflict, it surfaces one (CONSTITUTION.md leaves resolution to
        review, not silent overwrite)."""
        candidates = await self._repository.list_for_subject(record.user_id, record.subject_key)
        return [
            existing
            for existing in candidates
            if existing.memory_id != record.memory_id
            and conflicts_with(existing, record.subject_key, record.content)
        ]

    async def sweep_expired(self, user_id: str) -> list[MemoryRecord]:
        """Persists the CONFIRMED -> EXPIRED transition for any record past
        its expires_at, rather than only filtering at query time — expiry is
        a real lifecycle event (CONSTITUTION.md: Memory Lifecycle), auditable
        like every other transition."""
        now = self._clock.now_utc()
        records = await self._repository.list_for_user(user_id)
        expired: list[MemoryRecord] = []
        for record in records:
            if (
                record.status == MemoryStatus.CONFIRMED
                and record.expires_at
                and now >= record.expires_at
            ):
                updated = await self._transition(record, MemoryStatus.EXPIRED)
                await self._audit.record(
                    action="memory.expired",
                    result="success",
                    correlation_id=record.correlation_id,
                    detail={"memory_id": record.memory_id},
                )
                expired.append(updated)
        return expired

    async def retrieve_active(
        self, user_id: str, query: str = "", *, limit: int = 10
    ) -> list[MemoryRecord]:
        """Retrieval ranking (PROMPT.md Phase 9 implement item 7). Sweeps
        expiry first so a record whose time has lapsed can never surface
        here, matching the "deleted/expired memory no longer appears in
        retrieval" verification criterion for expiration as well as deletion."""
        await self.sweep_expired(user_id)
        now = self._clock.now_utc()
        records = await self._repository.list_for_user(user_id)
        active = [r for r in records if is_active(r, now)]

        if not query.strip():
            active.sort(key=lambda r: r.confirmed_at or r.created_at, reverse=True)
            return active[:limit]

        query_terms = frozenset(query.lower().split())
        active.sort(key=lambda r: rank_score(r, query_terms, now), reverse=True)
        return active[:limit]

    async def list_all_for_user(self, user_id: str) -> list[MemoryRecord]:
        """DOMAIN_OWNERSHIP.md: "User memory view" — every record regardless
        of status, so the user can see (and audit) candidates, confirmed
        facts, and their full supersession/expiration/deletion history."""
        return await self._repository.list_for_user(user_id)

    async def _require(self, memory_id: str) -> MemoryRecord:
        record = await self._repository.get(memory_id)
        if record is None:
            raise MemoryNotFoundError(f"no memory record {memory_id!r}")
        return record

    async def _transition(self, record: MemoryRecord, target: MemoryStatus) -> MemoryRecord:
        if not _is_valid_transition(record.status, target):
            raise InvalidMemoryStateTransitionError(
                f"{record.memory_id}: cannot move from {record.status} to {target}"
            )
        updated = record.model_copy(update={"status": target})
        await self._repository.save(updated)
        return updated
