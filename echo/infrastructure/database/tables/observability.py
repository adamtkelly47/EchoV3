"""Model call records (System — model-gateway telemetry, Docs/DATA_MODEL.md)
and tool call records (Capabilities — execution audit, Docs/DATA_MODEL.md).
Both feed the metrics Docs/CONSTITUTION.md's Observability section and
PROMPT.md Section 25 require: latency, token usage, cost, escalation rate,
approval conversion, retry count.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from infrastructure.database.base import Base


class ModelCallRow(Base):
    __tablename__ = "model_calls"

    call_id: Mapped[str] = mapped_column(String, primary_key=True)
    correlation_id: Mapped[str | None] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    model_name: Mapped[str] = mapped_column(String)
    task_type: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(String)
    # Only meaningful for generate_structured() calls (schema validation
    # doesn't apply to free-text generate()) — null there, not False.
    schema_valid: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolCallRow(Base):
    __tablename__ = "tool_calls"

    call_id: Mapped[str] = mapped_column(String, primary_key=True)
    correlation_id: Mapped[str | None] = mapped_column(String, index=True)
    capability_id: Mapped[str] = mapped_column(String, index=True)
    capability_version: Mapped[int] = mapped_column(Integer)
    permission_check_passed: Mapped[bool] = mapped_column(Boolean)
    approval_check_passed: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String, index=True)
    error_code: Mapped[str | None] = mapped_column(String)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    # Pre-redacted by the caller (CONSTITUTION.md: Secrets/Logging Philosophy).
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
