"""Database session management and transaction boundaries. Domains never
construct their own engine or session — they call `session_scope()`, which
is the one place a transaction begins and ends (CONSTITUTION.md: "Domain
modules must not... import a raw DB session directly" outside a repository).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import get_settings
from core.errors import ConfigurationError


def to_asyncpg_url(database_url: str) -> str:
    """Neon connection strings use the `postgresql://` scheme; SQLAlchemy's
    async engine needs the asyncpg dialect named explicitly. They also carry
    libpq-style query params (`sslmode`, `channel_binding`) that SQLAlchemy
    forwards verbatim as kwargs to `asyncpg.connect()` — which has no
    `sslmode` parameter (asyncpg uses `ssl=`, passed via `connect_args`
    instead, see `create_engine`), so `TypeError: connect() got an
    unexpected keyword argument 'sslmode'` unless they're stripped here.
    """
    parts = urlsplit(database_url)
    scheme = "postgresql+asyncpg" if parts.scheme == "postgresql" else parts.scheme
    return urlunsplit((scheme, parts.netloc, parts.path, "", parts.fragment))


def wants_ssl(database_url: str) -> bool:
    query = parse_qs(urlsplit(database_url).query)
    sslmode = query.get("sslmode", ["require"])[0]
    return sslmode != "disable"


def create_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or get_settings().database_url
    if not url:
        raise ConfigurationError("DATABASE_URL is not set")
    return create_async_engine(
        to_asyncpg_url(url),
        connect_args={
            # Neon's pooled ("-pooler") endpoint runs PgBouncer in
            # transaction mode, which does not support asyncpg's
            # server-side prepared-statement cache across pooled
            # connections — disabling it avoids intermittent protocol
            # errors under load. See Docs/decisions (Neon pooling notes).
            "statement_cache_size": 0,
            # asyncpg's own SSL param, translated from the URL's sslmode
            # (see to_asyncpg_url's docstring for why it can't stay in
            # the URL itself).
            "ssl": "require" if wants_ssl(url) else None,
        },
        # NullPool: Neon's own pooler already pools connections; a second
        # pool on top of it is redundant and can hide connection-limit
        # problems rather than surfacing them.
        poolclass=NullPool,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Process-wide engine singleton for application code. Tests construct
    their own engine via `create_engine()` rather than sharing this cache."""
    return create_engine()


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine or get_engine(), expire_on_commit=False)


@asynccontextmanager
async def session_scope(engine: AsyncEngine | None = None) -> AsyncIterator[AsyncSession]:
    """One transaction boundary per scope: commits on clean exit, rolls
    back on any exception. This is the only place a commit/rollback
    decision is made — repositories never commit their own session."""
    session = get_session_factory(engine)()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
