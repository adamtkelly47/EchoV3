"""Importing this package registers every table on `Base.metadata`, which
Alembic's `env.py` needs for autogeneration to see them all."""

from infrastructure.database.tables.audit import AuditEventRow
from infrastructure.database.tables.jobs import JobRow
from infrastructure.database.tables.observability import ModelCallRow, ToolCallRow
from infrastructure.database.tables.provenance import ComputedValueRecordRow, SourceRecordRow

__all__ = [
    "AuditEventRow",
    "ComputedValueRecordRow",
    "JobRow",
    "ModelCallRow",
    "SourceRecordRow",
    "ToolCallRow",
]
