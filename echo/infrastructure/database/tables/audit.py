"""Audit is mandatory for every significant action (CONSTITUTION.md: Audit
Philosophy). Owned by System (Docs/DATA_MODEL.md's State Categories table);
every acting domain writes here through `AuditRepository`, never its own
table, so "what happened, platform-wide" always has one place to look.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from infrastructure.database.base import Base


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    audit_id: Mapped[str] = mapped_column(String, primary_key=True)
    correlation_id: Mapped[str | None] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String, index=True)
    result: Mapped[str] = mapped_column(String)
    capability_id: Mapped[str | None] = mapped_column(String)
    provider: Mapped[str | None] = mapped_column(String)
    approval_id: Mapped[str | None] = mapped_column(String)
    verification_status: Mapped[str | None] = mapped_column(String)
    # Pre-redacted by the caller before persistence — this repository does
    # not redact (CONSTITUTION.md: "Redact sensitive payloads... Keep
    # secrets out of logs" applies equally to durable audit detail).
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
