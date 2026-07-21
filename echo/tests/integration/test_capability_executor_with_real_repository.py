"""Proves the executor composes correctly with the real Postgres-backed
ToolCallRepository — the unit tests use FakeToolCallRepository for speed,
but the Protocol contract needs to be proven against the real
implementation at least once (PROMPT.md Phase 4/5's "repository tests
pass against real PostgreSQL" spirit applied to a real consumer, not just
the repository in isolation).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import FakeClock
from domains.capabilities.service import CapabilityExecutor, CapabilityRegistry
from infrastructure.database.repositories.observability import PostgresToolCallRepository
from infrastructure.database.tables.observability import ToolCallRow
from tests.unit.domains.capabilities.fakes import make_echo_capability


async def test_execution_is_audited_via_real_repository(db_session: AsyncSession) -> None:
    registry = CapabilityRegistry()
    registry.register(make_echo_capability())
    tool_calls = PostgresToolCallRepository(db_session)
    executor = CapabilityExecutor(registry, tool_calls, FakeClock(datetime(2026, 1, 1, tzinfo=UTC)))

    result = await executor.execute(
        "test.echo", {"message": "hello"}, correlation_id="corr_integration_test"
    )
    assert result.message == "hello"

    rows = (
        (
            await db_session.execute(
                select(ToolCallRow).where(ToolCallRow.correlation_id == "corr_integration_test")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].capability_id == "test.echo"
    assert rows[0].status == "success"
