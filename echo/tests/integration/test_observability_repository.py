from datetime import UTC, datetime, timedelta

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


async def test_model_call_record_stores_schema_valid_and_list_since_finds_it(
    db_session: AsyncSession,
) -> None:
    """PROMPT.md Phase 25: `schema_valid` and `list_since` are this
    phase's own additions to a table that has existed since Phase 7."""
    repo = PostgresModelCallRepository(db_session)
    await repo.record(
        provider="ollama",
        model_name="llama3",
        task_type="classification",
        schema_valid=True,
        escalated=False,
    )
    since = datetime.now(UTC) - timedelta(minutes=1)
    rows = await repo.list_since(since)
    assert any(r.schema_valid is True for r in rows)


async def test_model_call_list_since_excludes_calls_before_the_window(
    db_session: AsyncSession,
) -> None:
    repo = PostgresModelCallRepository(db_session)
    await repo.record(provider="ollama", model_name="llama3", task_type="conversation")
    since = datetime.now(UTC) + timedelta(minutes=1)
    assert await repo.list_since(since) == []


async def test_tool_call_list_since_finds_a_recently_recorded_call(
    db_session: AsyncSession,
) -> None:
    repo = PostgresToolCallRepository(db_session)
    await repo.record(
        capability_id="observability_repo_test.capability",
        capability_version=1,
        permission_check_passed=True,
        status="success",
    )
    since = datetime.now(UTC) - timedelta(minutes=1)
    rows = await repo.list_since(since)
    assert any(r.capability_id == "observability_repo_test.capability" for r in rows)
