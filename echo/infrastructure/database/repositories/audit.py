"""Audit repository (CONSTITUTION.md: Audit is mandatory; audit records
must remain immutable — this repository has no update method, only
`record` (insert) and `get`/`list` (read)).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.identifiers import new_id
from infrastructure.database.tables.audit import AuditEventRow


class AuditRepository(Protocol):
    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str: ...

    async def get(self, audit_id: str) -> AuditEventRow | None: ...

    async def list_for_correlation(self, correlation_id: str) -> list[AuditEventRow]: ...

    async def list_recent_by_action(
        self, action: str, since: datetime, *, result: str | None = None
    ) -> list[AuditEventRow]: ...


class PostgresAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        row = AuditEventRow(
            audit_id=new_id("audit"),
            action=action,
            result=result,
            correlation_id=correlation_id,
            capability_id=capability_id,
            provider=provider,
            approval_id=approval_id,
            verification_status=verification_status,
            detail=detail,
        )
        self._session.add(row)
        await self._session.flush()
        return row.audit_id

    async def get(self, audit_id: str) -> AuditEventRow | None:
        return await self._session.get(AuditEventRow, audit_id)

    async def list_for_correlation(self, correlation_id: str) -> list[AuditEventRow]:
        result = await self._session.execute(
            select(AuditEventRow).where(AuditEventRow.correlation_id == correlation_id)
        )
        return list(result.scalars().all())

    async def list_recent_by_action(
        self, action: str, since: datetime, *, result: str | None = None
    ) -> list[AuditEventRow]:
        """PROMPT.md Phase 24's "integration failure" monitor is built
        directly on this — `calendar.token_refresh_failed`/
        `schwab.token_refresh_failed` are real audit actions every OAuth
        integration has recorded on failure since Phases 10-12, well
        before any monitoring concept existed."""
        conditions = [AuditEventRow.action == action, AuditEventRow.created_at >= since]
        if result is not None:
            conditions.append(AuditEventRow.result == result)
        query_result = await self._session.execute(select(AuditEventRow).where(*conditions))
        return list(query_result.scalars().all())
