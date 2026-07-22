"""Model call and tool call records — the raw data behind the metrics
Docs/CONSTITUTION.md's Observability section and PROMPT.md Section 25
require (latency, token usage, cost, escalation rate, retry count).

Phase 25 (evaluation and trust dashboard) is the first real reader of this
data — `list_since` was added alongside `TrustDashboardQueryService`
(application/queries/trust_dashboard_query.py), the first code anywhere in
this codebase that queries either table rather than only writing to it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.identifiers import new_id
from infrastructure.database.engine import session_scope
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
        schema_valid: bool | None = None,
    ) -> str: ...

    async def list_since(self, since: datetime) -> list[ModelCallRow]: ...


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

    async def list_since(self, since: datetime) -> list[ToolCallRow]: ...


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
        schema_valid: bool | None = None,
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
            schema_valid=schema_valid,
        )
        self._session.add(row)
        await self._session.flush()
        return row.call_id

    async def list_since(self, since: datetime) -> list[ModelCallRow]:
        result = await self._session.execute(
            select(ModelCallRow).where(ModelCallRow.created_at >= since)
        )
        return list(result.scalars().all())


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

    async def list_since(self, since: datetime) -> list[ToolCallRow]:
        result = await self._session.execute(
            select(ToolCallRow).where(ToolCallRow.created_at >= since)
        )
        return list(result.scalars().all())


class ModelCallRecorderPort(Protocol):
    """What `providers/models/gateway.py`'s `ModelGateway` depends on —
    narrower than the full `ModelCallRepository` (no `list_since`), and
    deliberately not session-scoped to the caller's own request
    transaction (see `StandaloneModelCallRecorder`)."""

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
        schema_valid: bool | None = None,
    ) -> str: ...


class StandaloneModelCallRecorder:
    """`ModelGateway` is a process-wide singleton with no request-scoped
    DB session of its own (apps/api/dependencies.py's `get_model_gateway`
    is `@lru_cache`'d). Model-call telemetry must not be lost or blocked
    by the caller's own business transaction (a rollback in, say,
    ConversationService should not also erase the fact that a model call
    happened) — so this recorder opens and commits its own short-lived
    session per call via `session_scope()`, exactly like
    `apps/worker/main.py`'s per-job pattern, rather than participating in
    whatever session the calling orchestrator happens to be using."""

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
        schema_valid: bool | None = None,
    ) -> str:
        async with session_scope() as session:
            return await PostgresModelCallRepository(session).record(
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
                schema_valid=schema_valid,
            )
