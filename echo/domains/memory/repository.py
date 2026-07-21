"""Memory owns durable knowledge about the user as a domain-owned aggregate
(CONSTITUTION.md: Aggregate Ownership — "MemoryRecord owns: confidence
bounds / supersession rules / review requirements."), so the ORM table lives
here rather than under infrastructure/database/tables/ — matching the
Approvals (Phase 6) and Conversation (Phase 8) precedent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import DateTime, Float, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.memory.models import MemoryStatus
from domains.memory.schemas import MemoryRecord
from infrastructure.database.base import Base


class MemoryRecordRow(Base):
    __tablename__ = "memory_records"

    memory_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    subject_key: Mapped[str] = mapped_column(String, index=True)
    content: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    correlation_id: Mapped[str | None] = mapped_column(String)
    supersedes_memory_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _to_row(record: MemoryRecord) -> MemoryRecordRow:
    return MemoryRecordRow(
        memory_id=record.memory_id,
        user_id=record.user_id,
        subject_key=record.subject_key,
        content=record.content,
        status=record.status.value,
        confidence=record.confidence,
        source_type=record.source_type,
        source_id=record.source_id,
        correlation_id=record.correlation_id,
        supersedes_memory_id=record.supersedes_memory_id,
        created_at=record.created_at,
        confirmed_at=record.confirmed_at,
        expires_at=record.expires_at,
    )


def _to_record(row: MemoryRecordRow) -> MemoryRecord:
    return MemoryRecord(
        memory_id=row.memory_id,
        user_id=row.user_id,
        subject_key=row.subject_key,
        content=row.content,
        status=MemoryStatus(row.status),
        confidence=row.confidence,
        source_type=row.source_type,
        source_id=row.source_id,
        correlation_id=row.correlation_id,
        supersedes_memory_id=row.supersedes_memory_id,
        created_at=row.created_at,
        confirmed_at=row.confirmed_at,
        expires_at=row.expires_at,
    )


class MemoryRepository(Protocol):
    async def save(self, record: MemoryRecord) -> None: ...
    async def get(self, memory_id: str) -> MemoryRecord | None: ...
    async def list_for_user(self, user_id: str) -> list[MemoryRecord]: ...
    async def list_for_subject(self, user_id: str, subject_key: str) -> list[MemoryRecord]: ...


class PostgresMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: MemoryRecord) -> None:
        existing = await self._session.get(MemoryRecordRow, record.memory_id)
        if existing is None:
            self._session.add(_to_row(record))
        else:
            self._update_row(existing, record)
        await self._session.flush()

    def _update_row(self, row: MemoryRecordRow, record: MemoryRecord) -> None:
        row.status = record.status.value
        row.confidence = record.confidence
        row.confirmed_at = record.confirmed_at
        row.expires_at = record.expires_at

    async def get(self, memory_id: str) -> MemoryRecord | None:
        row = await self._session.get(MemoryRecordRow, memory_id)
        return _to_record(row) if row is not None else None

    async def list_for_user(self, user_id: str) -> list[MemoryRecord]:
        result = await self._session.execute(
            select(MemoryRecordRow)
            .where(MemoryRecordRow.user_id == user_id)
            .order_by(MemoryRecordRow.created_at.asc())
        )
        return [_to_record(row) for row in result.scalars().all()]

    async def list_for_subject(self, user_id: str, subject_key: str) -> list[MemoryRecord]:
        result = await self._session.execute(
            select(MemoryRecordRow).where(
                MemoryRecordRow.user_id == user_id, MemoryRecordRow.subject_key == subject_key
            )
        )
        return [_to_record(row) for row in result.scalars().all()]
