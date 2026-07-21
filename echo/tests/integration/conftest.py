"""Integration tests need a real Postgres (Docs/TESTING.md: "PostgreSQL
repositories... against real PostgreSQL" per PROMPT.md Phase 4's own
verification criteria — a fake/mocked session would not prove the ORM
mappings, constraints, or Neon-pooler compatibility actually work).

Skips gracefully when DATABASE_URL isn't set (e.g. in CI, which has no
database credentials configured) rather than failing the run — see
Docs/TESTING.md's CI section.

Each test's session is never committed — only flushed within its own
transaction, then rolled back on teardown — so the real Neon dev branch
never accumulates test residue.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from infrastructure.database.engine import create_engine, get_session_factory


def require_database_url() -> str:
    url = get_settings().database_url
    if not url:
        pytest.skip("DATABASE_URL is not set — skipping integration tests")
    return url


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    url = require_database_url()
    engine = create_engine(url)
    session = get_session_factory(engine)()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()
