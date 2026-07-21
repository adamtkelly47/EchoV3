from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.repositories.audit import PostgresAuditRepository


async def test_record_and_get(db_session: AsyncSession) -> None:
    repo = PostgresAuditRepository(db_session)
    audit_id = await repo.record(
        action="capability.execute",
        result="success",
        correlation_id="corr_test_audit",
        capability_id="calendar.search_events",
        detail={"query": "meetings today"},
    )

    row = await repo.get(audit_id)
    assert row is not None
    assert row.action == "capability.execute"
    assert row.result == "success"
    assert row.detail == {"query": "meetings today"}


async def test_list_for_correlation(db_session: AsyncSession) -> None:
    repo = PostgresAuditRepository(db_session)
    await repo.record(action="a", result="success", correlation_id="corr_shared")
    await repo.record(action="b", result="success", correlation_id="corr_shared")
    await repo.record(action="c", result="success", correlation_id="corr_other")

    rows = await repo.list_for_correlation("corr_shared")
    assert {row.action for row in rows} == {"a", "b"}


async def test_get_missing_returns_none(db_session: AsyncSession) -> None:
    repo = PostgresAuditRepository(db_session)
    assert await repo.get("audit_does_not_exist") is None
