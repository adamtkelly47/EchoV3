"""Coordinates Memory + System for PROMPT.md Phase 25's "user corrections"
tracked item. No direct "Memory -> System" row exists in Docs/
DOMAIN_OWNERSHIP.md's Cross-Domain Interaction Matrix, but the matrix's own
general rule applies here exactly as it did for Phase 23's
ProjectMemoryOrchestrator: cross-domain coordination happens only through
the Application layer.

`domains/memory/service.py`'s `supersede()` already exists and is already
exposed at `POST /memory/{id}/supersede` for any caller — this orchestrator
is not a new way to correct a memory fact, it is the one, unambiguous entry
point that marks a correction as *user-initiated* (`source_type=
"user_correction"`), which is what lets `TrustDashboardQueryService` count
real corrections rather than every routine, orchestrator-driven
supersession (e.g. Phase 9's conflict resolution) as if it were one.
"""

from __future__ import annotations

from domains.memory.schemas import MemoryRecord
from domains.memory.service import MemoryService
from domains.system.schemas import RegressionCase
from domains.system.service import SystemService

_USER_CORRECTION_SOURCE_TYPE = "user_correction"


class TrustOrchestrator:
    def __init__(self, memory: MemoryService, system: SystemService) -> None:
        self._memory = memory
        self._system = system

    async def record_user_correction(
        self,
        memory_id: str,
        *,
        content: str,
        confidence: float,
        correlation_id: str | None = None,
    ) -> tuple[MemoryRecord, RegressionCase]:
        """PROMPT.md Phase 25: "user corrections" (tracked item 11) and
        "create regression datasets from corrected failures." The old
        record's own content is the incorrect output being corrected; the
        new content is what it should have said instead — exactly the
        shape a future regression check needs."""
        old = await self._memory.get(memory_id)
        superseded = await self._memory.supersede(
            memory_id,
            content=content,
            confidence=confidence,
            source_type=_USER_CORRECTION_SOURCE_TYPE,
            source_id=memory_id,
            correlation_id=correlation_id,
        )
        case = await self._system.record_regression_case(
            source_type=_USER_CORRECTION_SOURCE_TYPE,
            source_id=superseded.memory_id,
            incorrect_output=old.content,
            corrected_output=content,
        )
        return superseded, case
