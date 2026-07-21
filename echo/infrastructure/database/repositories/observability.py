"""Model call and tool call records — the raw data behind the metrics
Docs/CONSTITUTION.md's Observability section and PROMPT.md Section 25
require (latency, token usage, cost, escalation rate, retry count).
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from core.identifiers import new_id
from infrastructure.database.tables.observability import ModelCallRow, ToolCallRow


class ModelCallRepository(Protocol):
    async def record(
        self,
        *,
        provider: str,
        model_name: str,
        task_type: str,
        correlation_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: float | None = None,
        cost_estimate_usd: float | None = None,
        escalated: bool = False,
        escalation_reason: str | None = None,
    ) -> str: ...


class ToolCallRepository(Protocol):
    async def record(
        self,
        *,
        capability_id: str,
        capability_version: int,
        permission_check_passed: bool,
        status: str,
        correlation_id: str | None = None,
        approval_check_passed: bool | None = None,
        error_code: str | None = None,
        latency_ms: float | None = None,
        input_summary: dict[str, Any] | None = None,
    ) -> str: ...


class PostgresModelCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        provider: str,
        model_name: str,
        task_type: str,
        correlation_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: float | None = None,
        cost_estimate_usd: float | None = None,
        escalated: bool = False,
        escalation_reason: str | None = None,
    ) -> str:
        row = ModelCallRow(
            call_id=new_id("modelcall"),
            provider=provider,
            model_name=model_name,
            task_type=task_type,
            correlation_id=correlation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_estimate_usd=cost_estimate_usd,
            escalated=escalated,
            escalation_reason=escalation_reason,
        )
        self._session.add(row)
        await self._session.flush()
        return row.call_id


class PostgresToolCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        capability_id: str,
        capability_version: int,
        permission_check_passed: bool,
        status: str,
        correlation_id: str | None = None,
        approval_check_passed: bool | None = None,
        error_code: str | None = None,
        latency_ms: float | None = None,
        input_summary: dict[str, Any] | None = None,
    ) -> str:
        row = ToolCallRow(
            call_id=new_id("toolcall"),
            capability_id=capability_id,
            capability_version=capability_version,
            permission_check_passed=permission_check_passed,
            status=status,
            correlation_id=correlation_id,
            approval_check_passed=approval_check_passed,
            error_code=error_code,
            latency_ms=latency_ms,
            input_summary=input_summary,
        )
        self._session.add(row)
        await self._session.flush()
        return row.call_id
