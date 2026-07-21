"""Persisted form of core.provenance's SourceRecord/ComputedValueRecord.
One shared table, not one per domain: the row is conceptually "owned by
whichever domain the sourced data belongs to" (Docs/DATA_MODEL.md), but
that ownership is expressed by the domain row that references a record
here via foreign key — not by duplicating this table per domain.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.base import Base


class SourceRecordRow(Base):
    __tablename__ = "source_records"

    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    origin: Mapped[str] = mapped_column(String)
    external_id: Mapped[str | None] = mapped_column(String)
    # Pre-redacted by the caller — request params may include auth details
    # that must never reach durable storage (CONSTITUTION.md: Secrets).
    request_params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    response_hash: Mapped[str | None] = mapped_column(String)
    data_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_policy_seconds: Mapped[float | None] = mapped_column(Float)
    raw_storage_ref: Mapped[str | None] = mapped_column(String)
    parser_version: Mapped[str] = mapped_column(String)
    validation_status: Mapped[str] = mapped_column(String)
    error_state: Mapped[str | None] = mapped_column(String)


class ComputedValueRecordRow(Base):
    __tablename__ = "computed_value_records"

    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    calculation_name: Mapped[str] = mapped_column(String, index=True)
    calculation_version: Mapped[str] = mapped_column(String)
    input_record_ids: Mapped[list[str]] = mapped_column(JSONB)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    output: Mapped[Any] = mapped_column(JSONB)
    rounding_policy: Mapped[str | None] = mapped_column(String)
    validation_result: Mapped[str] = mapped_column(String)
