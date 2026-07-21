"""Fake test capabilities (PROMPT.md Phase 5: "fake test capabilities") and
a fake ToolCallRepository so the executor pipeline can be exercised without
a real database. Not production capabilities — nothing here is registered
outside tests.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from core.capabilities import CapabilityContract, ExecutionEnvironment, ReadWriteClassification
from core.security import Permission, PermissionAction
from domains.capabilities.models import RegisteredCapability


class EchoInput(BaseModel):
    message: str


class EchoOutput(BaseModel):
    message: str


async def _echo_handler(data: BaseModel) -> BaseModel:
    assert isinstance(data, EchoInput)
    return EchoOutput(message=data.message)


def make_echo_capability(capability_id: str = "test.echo") -> RegisteredCapability:
    """A read capability with no permission requirements — the baseline
    success path."""
    contract = CapabilityContract(
        capability_id=capability_id,
        version=1,
        display_name="Test Echo",
        description="Returns whatever input it received.",
        owner="System",
        input_schema=EchoInput.model_json_schema(),
        output_schema=EchoOutput.model_json_schema(),
        permission_requirements=[],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=5,
        idempotency_behavior="not applicable — read only",
        provenance_requirements="none — test fixture",
        supported_interfaces=["chat", "api"],
        expected_errors=[],
    )
    return RegisteredCapability(
        contract=contract, input_model=EchoInput, output_model=EchoOutput, handler=_echo_handler
    )


def make_permission_gated_capability(capability_id: str = "test.gated") -> RegisteredCapability:
    contract = CapabilityContract(
        capability_id=capability_id,
        version=1,
        display_name="Test Gated Echo",
        description="Same as test.echo but requires a permission.",
        owner="System",
        input_schema=EchoInput.model_json_schema(),
        output_schema=EchoOutput.model_json_schema(),
        permission_requirements=[
            Permission(resource="test.resource", action=PermissionAction.READ)
        ],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=5,
        idempotency_behavior="not applicable — read only",
        provenance_requirements="none — test fixture",
        supported_interfaces=["chat", "api"],
        expected_errors=[],
    )
    return RegisteredCapability(
        contract=contract, input_model=EchoInput, output_model=EchoOutput, handler=_echo_handler
    )


def make_write_capability(capability_id: str = "test.write") -> RegisteredCapability:
    """A write capability — proves the executor refuses to run it before
    the Approval Engine exists (Phase 6)."""
    contract = CapabilityContract(
        capability_id=capability_id,
        version=1,
        display_name="Test Write",
        description="A write capability that should never actually execute in Phase 5.",
        owner="System",
        input_schema=EchoInput.model_json_schema(),
        output_schema=EchoOutput.model_json_schema(),
        permission_requirements=[],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.WRITE,
        approval_requirement="test.write",
        timeout_seconds=5,
        idempotency_behavior="idempotency key required once execution exists",
        provenance_requirements="none — test fixture",
        supported_interfaces=["chat", "api"],
        expected_errors=[],
    )
    return RegisteredCapability(
        contract=contract, input_model=EchoInput, output_model=EchoOutput, handler=_echo_handler
    )


def make_slow_capability(
    capability_id: str = "test.slow", *, delay_seconds: float = 1.0, timeout_seconds: int = 1
) -> RegisteredCapability:
    async def slow_handler(data: BaseModel) -> BaseModel:
        assert isinstance(data, EchoInput)
        await asyncio.sleep(delay_seconds)
        return EchoOutput(message=data.message)

    contract = CapabilityContract(
        capability_id=capability_id,
        version=1,
        display_name="Test Slow",
        description="Sleeps longer than its own timeout, to test timeout handling.",
        owner="System",
        input_schema=EchoInput.model_json_schema(),
        output_schema=EchoOutput.model_json_schema(),
        permission_requirements=[],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=timeout_seconds,
        idempotency_behavior="not applicable — read only",
        provenance_requirements="none — test fixture",
        supported_interfaces=["chat", "api"],
        expected_errors=["timeout_error"],
    )
    return RegisteredCapability(
        contract=contract, input_model=EchoInput, output_model=EchoOutput, handler=slow_handler
    )


def make_failing_capability(capability_id: str = "test.failing") -> RegisteredCapability:
    async def failing_handler(data: BaseModel) -> BaseModel:
        raise RuntimeError("deliberate failure for testing error normalization")

    contract = CapabilityContract(
        capability_id=capability_id,
        version=1,
        display_name="Test Failing",
        description="Always raises an unnormalized error, to test error normalization.",
        owner="System",
        input_schema=EchoInput.model_json_schema(),
        output_schema=EchoOutput.model_json_schema(),
        permission_requirements=[],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=5,
        idempotency_behavior="not applicable — read only",
        provenance_requirements="none — test fixture",
        supported_interfaces=["chat", "api"],
        expected_errors=["unexpected_error"],
    )
    return RegisteredCapability(
        contract=contract, input_model=EchoInput, output_model=EchoOutput, handler=failing_handler
    )


class FakeToolCallRepository:
    """In-memory ToolCallRepository — same Protocol as the Postgres-backed
    one, so executor tests don't need a real database."""

    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

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
        call_id = f"toolcall_fake_{len(self.recorded)}"
        self.recorded.append(
            {
                "call_id": call_id,
                "capability_id": capability_id,
                "capability_version": capability_version,
                "permission_check_passed": permission_check_passed,
                "status": status,
                "correlation_id": correlation_id,
                "approval_check_passed": approval_check_passed,
                "error_code": error_code,
                "latency_ms": latency_ms,
                "input_summary": input_summary,
            }
        )
        return call_id
