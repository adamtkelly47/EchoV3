from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class _FakeAuditEventRow:
    audit_id: str
    action: str
    result: str
    correlation_id: str | None
    detail: dict[str, Any] | None
    created_at: datetime


class FakeObservabilityAuditRepository:
    """Attribute-style rows (`.detail`, `.result`, ...) matching the real
    `AuditEventRow` ORM object `AuditRepository.list_recent_by_action`
    returns — unlike `tests/unit/domains/system/fakes.py`'s own
    `FakeAuditRepository`, which returns plain dicts and is only ever read
    via dict subscript by existing tests, never via attribute access."""

    def __init__(self) -> None:
        self._rows: list[_FakeAuditEventRow] = []

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        audit_id = f"audit_fake_{len(self._rows)}"
        self._rows.append(
            _FakeAuditEventRow(
                audit_id=audit_id,
                action=action,
                result=result,
                correlation_id=correlation_id,
                detail=detail,
                created_at=datetime.now(),
            )
        )
        return audit_id

    async def get(self, audit_id: str) -> Any:
        return next((r for r in self._rows if r.audit_id == audit_id), None)

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [r for r in self._rows if r.correlation_id == correlation_id]

    async def list_recent_by_action(
        self, action: str, since: datetime, *, result: str | None = None
    ) -> list[_FakeAuditEventRow]:
        rows = [r for r in self._rows if r.action == action]
        if result is not None:
            rows = [r for r in rows if r.result == result]
        return rows


@dataclass
class _FakeModelCallRow:
    call_id: str
    provider: str
    model_name: str
    task_type: str
    correlation_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float | None
    cost_estimate_usd: float | None
    escalated: bool
    escalation_reason: str | None
    schema_valid: bool | None
    created_at: datetime


class FakeModelCallRepository:
    def __init__(self) -> None:
        self._rows: list[_FakeModelCallRow] = []

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
        call_id = f"modelcall_fake_{len(self._rows)}"
        self._rows.append(
            _FakeModelCallRow(
                call_id=call_id,
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
                created_at=datetime.now(),
            )
        )
        return call_id

    async def list_since(self, since: datetime) -> list[_FakeModelCallRow]:
        return list(self._rows)


@dataclass
class _FakeToolCallRow:
    call_id: str
    capability_id: str
    capability_version: int
    permission_check_passed: bool
    approval_check_passed: bool | None
    status: str
    correlation_id: str | None
    error_code: str | None
    latency_ms: float | None
    input_summary: dict[str, Any] | None
    created_at: datetime


class FakeToolCallRepository:
    def __init__(self) -> None:
        self._rows: list[_FakeToolCallRow] = []

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
        call_id = f"toolcall_fake_{len(self._rows)}"
        self._rows.append(
            _FakeToolCallRow(
                call_id=call_id,
                capability_id=capability_id,
                capability_version=capability_version,
                permission_check_passed=permission_check_passed,
                approval_check_passed=approval_check_passed,
                status=status,
                correlation_id=correlation_id,
                error_code=error_code,
                latency_ms=latency_ms,
                input_summary=input_summary,
                created_at=datetime.now(),
            )
        )
        return call_id

    async def list_since(self, since: datetime) -> list[_FakeToolCallRow]:
        return list(self._rows)
