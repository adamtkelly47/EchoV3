from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.repositories.observability import (
    PostgresModelCallRepository,
    PostgresToolCallRepository,
)


async def test_model_call_record(db_session: AsyncSession) -> None:
    repo = PostgresModelCallRepository(db_session)
    call_id = await repo.record(
        provider="ollama",
        model_name="llama3",
        task_type="classification",
        input_tokens=120,
        output_tokens=40,
        latency_ms=350.5,
        escalated=False,
    )
    assert call_id.startswith("modelcall_")


async def test_tool_call_record(db_session: AsyncSession) -> None:
    repo = PostgresToolCallRepository(db_session)
    call_id = await repo.record(
        capability_id="calendar.search_events",
        capability_version=1,
        permission_check_passed=True,
        status="success",
        latency_ms=42.0,
    )
    assert call_id.startswith("toolcall_")
