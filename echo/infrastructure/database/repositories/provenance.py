"""Persists/retrieves the core.provenance contracts. Repositories take and
return the core Pydantic types, not ORM rows — callers never see a
SQLAlchemy object, matching CONSTITUTION.md's Typed Contracts rule at the
persistence boundary.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from core.provenance import ComputedValueRecord, SourceRecord, ValidationStatus
from infrastructure.database.tables.provenance import ComputedValueRecordRow, SourceRecordRow


class SourceRecordRepository(Protocol):
    async def save(self, record: SourceRecord) -> None: ...
    async def get(self, record_id: str) -> SourceRecord | None: ...


class ComputedValueRecordRepository(Protocol):
    async def save(self, record: ComputedValueRecord) -> None: ...
    async def get(self, record_id: str) -> ComputedValueRecord | None: ...


def _source_record_to_row(record: SourceRecord) -> SourceRecordRow:
    return SourceRecordRow(
        record_id=record.record_id,
        source_type=record.source_type,
        provider=record.provider,
        retrieved_at=record.retrieved_at,
        origin=record.origin,
        external_id=record.external_id,
        request_params=record.request_params,
        response_hash=record.response_hash,
        data_effective_at=record.data_effective_at,
        freshness_policy_seconds=(
            record.freshness_policy.total_seconds() if record.freshness_policy else None
        ),
        raw_storage_ref=record.raw_storage_ref,
        parser_version=record.parser_version,
        validation_status=record.validation_status.value,
        error_state=record.error_state,
    )


def _row_to_source_record(row: SourceRecordRow) -> SourceRecord:
    return SourceRecord(
        record_id=row.record_id,
        source_type=row.source_type,
        provider=row.provider,
        retrieved_at=row.retrieved_at,
        origin=row.origin,
        external_id=row.external_id,
        request_params=row.request_params,
        response_hash=row.response_hash,
        data_effective_at=row.data_effective_at,
        freshness_policy=(
            timedelta(seconds=row.freshness_policy_seconds)
            if row.freshness_policy_seconds is not None
            else None
        ),
        raw_storage_ref=row.raw_storage_ref,
        parser_version=row.parser_version,
        validation_status=ValidationStatus(row.validation_status),
        error_state=row.error_state,
    )


class PostgresSourceRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: SourceRecord) -> None:
        self._session.add(_source_record_to_row(record))
        await self._session.flush()

    async def get(self, record_id: str) -> SourceRecord | None:
        row = await self._session.get(SourceRecordRow, record_id)
        return _row_to_source_record(row) if row is not None else None


class PostgresComputedValueRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: ComputedValueRecord) -> None:
        row = ComputedValueRecordRow(
            record_id=record.record_id,
            calculation_name=record.calculation_name,
            calculation_version=record.calculation_version,
            input_record_ids=record.input_record_ids,
            executed_at=record.executed_at,
            output=record.output,
            rounding_policy=record.rounding_policy,
            validation_result=record.validation_result.value,
        )
        self._session.add(row)
        await self._session.flush()

    async def get(self, record_id: str) -> ComputedValueRecord | None:
        row = await self._session.get(ComputedValueRecordRow, record_id)
        if row is None:
            return None
        return ComputedValueRecord(
            record_id=row.record_id,
            calculation_name=row.calculation_name,
            calculation_version=row.calculation_version,
            input_record_ids=row.input_record_ids,
            executed_at=row.executed_at,
            output=row.output,
            rounding_policy=row.rounding_policy,
            validation_result=ValidationStatus(row.validation_result),
        )
