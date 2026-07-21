from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.memory.models import MemoryStatus
from domains.memory.repository import PostgresMemoryRepository
from domains.memory.schemas import MemoryRecord


async def test_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresMemoryRepository(db_session)
    record = MemoryRecord(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="The user's favorite color is blue.",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
        correlation_id="corr_1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    await repo.save(record)
    restored = await repo.get(record.memory_id)

    assert restored is not None
    assert restored.status == MemoryStatus.CANDIDATE
    assert restored.content == "The user's favorite color is blue."
    assert restored.correlation_id == "corr_1"


async def test_status_and_confirmed_at_transitions_persist(db_session: AsyncSession) -> None:
    repo = PostgresMemoryRepository(db_session)
    record = MemoryRecord(
        user_id="user_1",
        subject_key="k",
        content="c",
        confidence=0.5,
        source_type="conversation",
        source_id="msg_1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save(record)

    confirmed = record.model_copy(
        update={"status": MemoryStatus.CONFIRMED, "confirmed_at": datetime(2026, 1, 2, tzinfo=UTC)}
    )
    await repo.save(confirmed)

    restored = await repo.get(record.memory_id)
    assert restored is not None
    assert restored.status == MemoryStatus.CONFIRMED
    assert restored.confirmed_at == datetime(2026, 1, 2, tzinfo=UTC)


async def test_list_for_subject_scopes_to_user_and_subject_key(db_session: AsyncSession) -> None:
    repo = PostgresMemoryRepository(db_session)
    matching = MemoryRecord(
        user_id="user_1",
        subject_key="user.favorite_color",
        content="blue",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    other_subject = MemoryRecord(
        user_id="user_1",
        subject_key="user.location",
        content="Seattle",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_2",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    other_user = MemoryRecord(
        user_id="user_2",
        subject_key="user.favorite_color",
        content="red",
        confidence=0.9,
        source_type="conversation",
        source_id="msg_3",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save(matching)
    await repo.save(other_subject)
    await repo.save(other_user)

    results = await repo.list_for_subject("user_1", "user.favorite_color")
    assert [r.memory_id for r in results] == [matching.memory_id]


async def test_list_for_user_returns_every_status(db_session: AsyncSession) -> None:
    repo = PostgresMemoryRepository(db_session)
    record = MemoryRecord(
        user_id="user_1",
        subject_key="k",
        content="c",
        confidence=0.5,
        source_type="conversation",
        source_id="msg_1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save(record)
    deleted = record.model_copy(update={"status": MemoryStatus.DELETED})
    await repo.save(deleted)

    results = await repo.list_for_user("user_1")
    assert len(results) == 1
    assert results[0].status == MemoryStatus.DELETED
