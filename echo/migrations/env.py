"""Alembic environment. Runs migrations against the async engine (same
asyncpg driver the app uses — see infrastructure/database/engine.py's
pooling notes for why `statement_cache_size=0` matters against Neon's
pooled endpoint), so adding a second, migration-only DB driver is avoided.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from core.config import get_settings
from core.errors import ConfigurationError
from domains.approvals.repository import (  # noqa: F401 — registers tables on Base.metadata
    ApprovalDecisionRow,
    ApprovalProposalRow,
)
from infrastructure.database.base import Base
from infrastructure.database.engine import create_engine, to_asyncpg_url
from infrastructure.database.tables import (  # noqa: F401 — registers tables on Base.metadata
    AuditEventRow,
    ComputedValueRecordRow,
    JobRow,
    ModelCallRow,
    SourceRecordRow,
    ToolCallRow,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _require_database_url() -> str:
    url = get_settings().database_url
    if not url:
        raise ConfigurationError("DATABASE_URL is not set")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=to_asyncpg_url(_require_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Reuses the app's own create_engine() rather than building a second,
    # separately-configured engine here — the Neon-pooler connect_args
    # (statement_cache_size, ssl) only need to be correct in one place.
    connectable = create_engine(_require_database_url())

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
