"""Typed provenance contracts, matching Docs/DATA_MODEL.md's Provenance
Model exactly. Every normalized object derived from an external system must
be connectable to a SourceRecord; every computed value must record a
ComputedValueRecord identifying its inputs (CONSTITUTION.md: Provenance —
"Every computed value must remain reproducible.").

These are pure contracts — no persistence, no domain logic. Repositories
(Phase 4+) store them; domains attach them to the data they produce.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.identifiers import new_id


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


class SourceRecord(BaseModel):
    """Where a piece of externally derived data came from."""

    model_config = ConfigDict(frozen=True)

    # default_factory, not `= new_id(...)` — a bare default would evaluate
    # once at class-definition time and give every instance the same id.
    record_id: str = Field(default_factory=lambda: new_id("source"))
    source_type: str
    provider: str
    retrieved_at: datetime
    origin: str
    external_id: str | None = None
    request_params: dict[str, Any] = {}
    response_hash: str | None = None
    data_effective_at: datetime | None = None
    freshness_policy: timedelta | None = None
    raw_storage_ref: str | None = None
    parser_version: str
    validation_status: ValidationStatus
    error_state: str | None = None


class ComputedValueRecord(BaseModel):
    """How a value was calculated, and from what — makes every computed
    number in Echo answerable with "where did that come from?" """

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(default_factory=lambda: new_id("computed"))
    calculation_name: str
    calculation_version: str
    input_record_ids: list[str]
    executed_at: datetime
    output: Any
    rounding_policy: str | None = None
    validation_result: ValidationStatus
