"""Directly proves PROMPT.md Phase 9's four verification criteria against
domains.memory.service.MemoryService, matching the pattern established by
tests/unit/application/orchestrators/test_conversation_orchestrator.py for
Phase 8's own verification criteria.
"""

from datetime import UTC, datetime

import pytest

from core.time import FakeClock
from domains.memory.errors import InvalidMemoryStateTransitionError, MemoryNotFoundError
from domains.memory.models import MemoryStatus
from domains.memory.service import MemoryService
from tests.unit.domains.memory.fakes import FakeAuditRepository, FakeMemoryRepository


def _service(clock: FakeClock | None = None) -> MemoryService:
    return MemoryService(
        FakeMemoryRepository(),
        FakeAuditRepository(),
        clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )


async def test_extracted_candidates_are_not_automatically_confirmed() -> None:
    """PROMPT.md Phase 9 verification 1."""
    service = _service()
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    assert record.status == MemoryStatus.CANDIDATE
    assert record.confirmed_at is None


async def test_confirm_transitions_candidate_to_confirmed() -> None:
    service = _service()
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    confirmed = await service.confirm(record.memory_id)
    assert confirmed.status == MemoryStatus.CONFIRMED
    assert confirmed.confirmed_at is not None


async def test_confirming_an_already_confirmed_memory_is_rejected() -> None:
    service = _service()
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="k",
        content="c",
        confidence=0.5,
        source_type="conversation",
        source_id="msg_1",
    )
    await service.confirm(record.memory_id)
    with pytest.raises(InvalidMemoryStateTransitionError):
        await service.confirm(record.memory_id)


async def test_conflicting_memories_are_detectable() -> None:
    """PROMPT.md Phase 9 verification 2."""
    service = _service()
    first = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    await service.confirm(first.memory_id)

    second = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is green.",
        confidence=0.8,
        source_type="conversation",
        source_id="msg_2",
    )
    confirmed_second = await service.confirm(second.memory_id)

    conflicts = await service.detect_conflicts(confirmed_second)
    assert [c.memory_id for c in conflicts] == [first.memory_id]


async def test_agreeing_memories_are_not_flagged_as_conflicts() -> None:
    service = _service()
    first = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    await service.confirm(first.memory_id)

    second = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_2",
    )
    confirmed_second = await service.confirm(second.memory_id)

    assert await service.detect_conflicts(confirmed_second) == []


async def test_deleted_memory_no_longer_appears_in_retrieval() -> None:
    """PROMPT.md Phase 9 verification 3."""
    service = _service()
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    await service.confirm(record.memory_id)
    assert len(await service.retrieve_active("user_1")) == 1

    await service.delete(record.memory_id)
    assert await service.retrieve_active("user_1") == []


async def test_expired_memory_no_longer_appears_in_retrieval() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service = _service(clock)
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
        expires_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await service.confirm(record.memory_id)

    assert len(await service.retrieve_active("user_1")) == 1
    clock.set(datetime(2026, 1, 3, tzinfo=UTC))
    assert await service.retrieve_active("user_1") == []

    persisted = await service.get(record.memory_id)
    assert persisted.status == MemoryStatus.EXPIRED


async def test_source_context_remains_traceable() -> None:
    """PROMPT.md Phase 9 verification 4."""
    service = _service()
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_42",
        correlation_id="corr_1",
    )
    persisted = await service.get(record.memory_id)
    assert persisted.source_type == "conversation"
    assert persisted.source_id == "msg_42"
    assert persisted.correlation_id == "corr_1"


async def test_supersede_replaces_old_memory_and_preserves_lineage() -> None:
    service = _service()
    old = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    await service.confirm(old.memory_id)

    new = await service.supersede(
        old.memory_id,
        content="The user's favorite color is green.",
        confidence=0.95,
        source_type="conversation",
        source_id="msg_5",
    )

    assert new.status == MemoryStatus.CONFIRMED
    assert new.supersedes_memory_id == old.memory_id

    old_after = await service.get(old.memory_id)
    assert old_after.status == MemoryStatus.SUPERSEDED

    active = await service.retrieve_active("user_1")
    assert [r.memory_id for r in active] == [new.memory_id]


async def test_operations_on_unknown_memory_raise_not_found() -> None:
    service = _service()
    with pytest.raises(MemoryNotFoundError):
        await service.confirm("does-not-exist")


async def test_list_all_for_user_includes_every_status() -> None:
    """DOMAIN_OWNERSHIP.md: "User memory view" — unlike retrieve_active,
    this shows candidates and deleted/superseded/expired history too."""
    service = _service()
    candidate = await service.record_candidate(
        user_id="user_1",
        subject_key="k",
        content="c",
        confidence=0.5,
        source_type="conversation",
        source_id="msg_1",
    )
    confirmed = await service.record_candidate(
        user_id="user_1",
        subject_key="k2",
        content="c2",
        confidence=0.5,
        source_type="conversation",
        source_id="msg_2",
    )
    await service.confirm(confirmed.memory_id)
    await service.delete(candidate.memory_id)

    all_records = await service.list_all_for_user("user_1")
    assert {r.status for r in all_records} == {MemoryStatus.DELETED, MemoryStatus.CONFIRMED}


async def test_retrieve_active_ranks_by_query_relevance() -> None:
    service = _service()
    color = await service.record_candidate(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
    )
    location = await service.record_candidate(
        user_id="user_1",
        subject_key="user.location",
        content="The user lives in Seattle.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_2",
    )
    await service.confirm(color.memory_id)
    await service.confirm(location.memory_id)

    results = await service.retrieve_active("user_1", "favorite color")
    assert results[0].memory_id == color.memory_id


async def test_confidence_is_clamped_to_zero_one() -> None:
    service = _service()
    record = await service.record_candidate(
        user_id="user_1",
        subject_key="k",
        content="c",
        confidence=5.0,
        source_type="conversation",
        source_id="msg_1",
    )
    assert record.confidence == 1.0
