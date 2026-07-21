"""CapabilityRegistry: discovery — capabilities are found by registration,
never by keyword lists or hardcoded routing (CONSTITUTION.md: Capability
Discovery). CapabilityExecutor: runs the Constitution's Capability Execution
pipeline — registry lookup, input validation, permission check, execution,
output validation, audit recording. Every attempt is audited exactly once,
in a `finally` block, so a failure at any stage still produces a tool call
record (Docs/CAPABILITY_REGISTRY.md: "Tool calls are auditable").
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from core.errors import AuthorizationError, EchoError, EchoTimeoutError, UnexpectedError
from core.errors import ValidationError as EchoValidationError
from core.security import Permission
from core.time import Clock
from domains.capabilities.errors import (
    CapabilityAlreadyRegisteredError,
    CapabilityNotFoundError,
    WriteCapabilityNotExecutableError,
)
from domains.capabilities.models import RegisteredCapability
from domains.capabilities.policies import has_required_permissions, is_executable_now
from infrastructure.database.repositories.observability import ToolCallRepository


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, RegisteredCapability] = {}

    def register(self, capability: RegisteredCapability) -> None:
        key = capability.contract.capability_id
        if key in self._capabilities:
            raise CapabilityAlreadyRegisteredError(f"{key} is already registered")
        self._capabilities[key] = capability

    def get(self, capability_id: str) -> RegisteredCapability:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise CapabilityNotFoundError(f"no capability registered as {capability_id!r}") from exc

    def list_contracts(self) -> list[Any]:
        return [c.contract for c in self._capabilities.values()]


class CapabilityExecutor:
    def __init__(
        self,
        registry: CapabilityRegistry,
        tool_call_repository: ToolCallRepository,
        clock: Clock,
    ) -> None:
        self._registry = registry
        self._tool_calls = tool_call_repository
        self._clock = clock

    async def execute(
        self,
        capability_id: str,
        raw_input: dict[str, Any],
        *,
        granted_permissions: frozenset[Permission] = frozenset(),
        correlation_id: str | None = None,
    ) -> BaseModel:
        capability = self._registry.get(capability_id)
        permission_ok = has_required_permissions(
            capability.contract.permission_requirements, granted_permissions
        )
        start = self._clock.monotonic()
        status = "success"
        error_code: str | None = None

        try:
            if not permission_ok:
                raise AuthorizationError(f"missing required permissions for {capability_id}")
            if not is_executable_now(capability.contract):
                raise WriteCapabilityNotExecutableError(
                    f"{capability_id} is a write capability; not executable before the "
                    f"Approval Engine exists (Phase 6)"
                )
            validated_input = self._validate_input(capability, raw_input)
            output = await self._run_handler(capability, validated_input)
            self._validate_output(capability, output)
            return output
        except EchoError as exc:
            status = "failure"
            error_code = exc.code
            raise
        except Exception as exc:
            status = "failure"
            error_code = UnexpectedError.code
            raise UnexpectedError(f"{capability_id} raised an unexpected error") from exc
        finally:
            latency_ms = (self._clock.monotonic() - start) * 1000
            await self._tool_calls.record(
                capability_id=capability_id,
                capability_version=capability.contract.version,
                permission_check_passed=permission_ok,
                status=status,
                error_code=error_code,
                latency_ms=latency_ms,
                correlation_id=correlation_id,
            )

    def _validate_input(
        self, capability: RegisteredCapability, raw_input: dict[str, Any]
    ) -> BaseModel:
        try:
            return capability.input_model.model_validate(raw_input)
        except PydanticValidationError as exc:
            raise EchoValidationError(
                f"invalid input for {capability.contract.capability_id}", detail=str(exc)
            ) from exc

    async def _run_handler(
        self, capability: RegisteredCapability, validated_input: BaseModel
    ) -> BaseModel:
        try:
            return await asyncio.wait_for(
                capability.handler(validated_input), timeout=capability.contract.timeout_seconds
            )
        except TimeoutError as exc:
            raise EchoTimeoutError(
                f"{capability.contract.capability_id} timed out after "
                f"{capability.contract.timeout_seconds}s"
            ) from exc

    def _validate_output(self, capability: RegisteredCapability, output: BaseModel) -> None:
        if not isinstance(output, capability.output_model):
            raise EchoValidationError(
                f"{capability.contract.capability_id} handler returned "
                f"{type(output).__name__}, expected {capability.output_model.__name__}"
            )
