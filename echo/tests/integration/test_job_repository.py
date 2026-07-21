from sqlalchemy.ext.asyncio import AsyncSession

from core.identifiers import new_id
from infrastructure.database.repositories.jobs import PostgresJobRepository


async def test_save_and_get(db_session: AsyncSession) -> None:
    repo = PostgresJobRepository(db_session)
    job_id = new_id("job")
    idempotency_key = new_id("idem")

    await repo.save(
        job_id=job_id,
        job_type="system.ping",
        job_version=1,
        input={"note": "hello"},
        idempotency_key=idempotency_key,
        retry_policy={"max_attempts": 3},
        timeout_seconds=30,
        correlation_id="corr_job_test",
    )

    row = await repo.get(job_id)
    assert row is not None
    assert row.status == "pending"
    assert row.attempts == 0
    assert row.input == {"note": "hello"}


async def test_idempotency_key_is_unique(db_session: AsyncSession) -> None:
    repo = PostgresJobRepository(db_session)
    idempotency_key = new_id("idem")

    await repo.save(
        job_id=new_id("job"),
        job_type="system.ping",
        job_version=1,
        input={},
        idempotency_key=idempotency_key,
        retry_policy={},
        timeout_seconds=30,
    )
    await db_session.flush()

    found = await repo.get_by_idempotency_key(idempotency_key)
    assert found is not None
    assert found.idempotency_key == idempotency_key


async def test_update_status_transitions(db_session: AsyncSession) -> None:
    repo = PostgresJobRepository(db_session)
    job_id = new_id("job")
    await repo.save(
        job_id=job_id,
        job_type="system.ping",
        job_version=1,
        input={},
        idempotency_key=new_id("idem"),
        retry_policy={},
        timeout_seconds=30,
    )

    await repo.update_status(job_id, status="running", attempts=1)
    row = await repo.get(job_id)
    assert row is not None
    assert row.status == "running"
    assert row.attempts == 1

    await repo.update_status(job_id, status="failed", failure_classification="transient")
    row = await repo.get(job_id)
    assert row is not None
    assert row.status == "failed"
    assert row.failure_classification == "transient"
