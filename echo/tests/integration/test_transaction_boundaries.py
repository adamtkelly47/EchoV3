"""Proves infrastructure.database.engine.session_scope's commit/rollback
contract for real, against real Postgres — PROMPT.md Phase 4's explicit
verification criterion ("Transaction rollback behavior is verified").
Uses session_scope directly rather than the db_session fixture, since this
test is specifically about session_scope's own commit/rollback behavior.
"""

from infrastructure.database.engine import create_engine, session_scope
from infrastructure.database.repositories.audit import PostgresAuditRepository
from infrastructure.database.tables.audit import AuditEventRow
from tests.integration.conftest import require_database_url


async def test_rollback_discards_uncommitted_changes() -> None:
    url = require_database_url()
    engine = create_engine(url)
    try:
        audit_id: str | None = None
        try:
            async with session_scope(engine) as session:
                audit_id = await PostgresAuditRepository(session).record(
                    action="rollback.test", result="success"
                )
                raise RuntimeError("deliberate failure to trigger rollback")
        except RuntimeError:
            pass

        assert audit_id is not None
        async with session_scope(engine) as verify_session:
            row = await verify_session.get(AuditEventRow, audit_id)
            assert row is None, "row should not exist — the transaction was rolled back"
    finally:
        await engine.dispose()


async def test_commit_persists_changes() -> None:
    url = require_database_url()
    engine = create_engine(url)
    audit_id: str | None = None
    try:
        async with session_scope(engine) as session:
            audit_id = await PostgresAuditRepository(session).record(
                action="commit.test", result="success"
            )

        async with session_scope(engine) as verify_session:
            row = await verify_session.get(AuditEventRow, audit_id)
            assert row is not None, "row should exist — the transaction was committed"
    finally:
        # This path commits for real (unlike the db_session fixture used
        # elsewhere), so it cleans up its own row explicitly.
        if audit_id is not None:
            async with session_scope(engine) as cleanup_session:
                row = await cleanup_session.get(AuditEventRow, audit_id)
                if row is not None:
                    await cleanup_session.delete(row)
        await engine.dispose()
