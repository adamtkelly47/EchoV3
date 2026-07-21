"""Persists jobs (see core.jobs.JobEnvelope for the shape a caller builds
before saving). Idempotency is enforced at the database level via a unique
constraint on `idempotency_key` (CONSTITUTION.md: Idempotency — "Retries
should never duplicate write operations unless idempotency guarantees
exist.").
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.tables.jobs import JobRow


class JobRepository(Protocol):
    async def save(
        self,
        *,
        job_id: str,
        job_type: str,
        job_version: int,
        input: dict[str, Any],
        idempotency_key: str,
        retry_policy: dict[str, Any],
        timeout_seconds: int,
        correlation_id: str | None = None,
    ) -> None: ...

    async def get(self, job_id: str) -> JobRow | None: ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRow | None: ...

    async def update_status(
        self,
        job_id: str,
        *,
        status: str,
        attempts: int | None = None,
        failure_classification: str | None = None,
    ) -> None: ...


class PostgresJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        *,
        job_id: str,
        job_type: str,
        job_version: int,
        input: dict[str, Any],
        idempotency_key: str,
        retry_policy: dict[str, Any],
        timeout_seconds: int,
        correlation_id: str | None = None,
    ) -> None:
        row = JobRow(
            job_id=job_id,
            job_type=job_type,
            job_version=job_version,
            input=input,
            idempotency_key=idempotency_key,
            retry_policy=retry_policy,
            timeout_seconds=timeout_seconds,
            correlation_id=correlation_id,
        )
        self._session.add(row)
        await self._session.flush()

    async def get(self, job_id: str) -> JobRow | None:
        return await self._session.get(JobRow, job_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRow | None:
        result = await self._session.execute(
            select(JobRow).where(JobRow.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: str,
        *,
        status: str,
        attempts: int | None = None,
        failure_classification: str | None = None,
    ) -> None:
        row = await self._session.get(JobRow, job_id)
        if row is None:
            return
        row.status = status
        if attempts is not None:
            row.attempts = attempts
        if failure_classification is not None:
            row.failure_classification = failure_classification
        await self._session.flush()
