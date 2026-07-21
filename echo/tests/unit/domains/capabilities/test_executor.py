from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from core.errors import AuthorizationError, EchoTimeoutError, UnexpectedError
from core.errors import ValidationError as EchoValidationError
from core.security import Permission, PermissionAction
from core.time import FakeClock
from domains.capabilities.errors import WriteCapabilityNotExecutableError
from domains.capabilities.models import RegisteredCapability
from domains.capabilities.service import CapabilityExecutor, CapabilityRegistry
from tests.unit.domains.capabilities.fakes import (
    EchoInput,
    EchoOutput,
    FakeToolCallRepository,
    make_echo_capability,
    make_failing_capability,
    make_permission_gated_capability,
    make_slow_capability,
    make_write_capability,
)


def _executor() -> tuple[CapabilityExecutor, CapabilityRegistry, FakeToolCallRepository]:
    registry = CapabilityRegistry()
    tool_calls = FakeToolCallRepository()
    executor = CapabilityExecutor(registry, tool_calls, FakeClock(datetime(2026, 1, 1, tzinfo=UTC)))
    return executor, registry, tool_calls


async def test_successful_execution_returns_typed_output() -> None:
    executor, registry, _ = _executor()
    registry.register(make_echo_capability())

    result = await executor.execute("test.echo", {"message": "hello"})

    assert isinstance(result, EchoOutput)
    assert result.message == "hello"


async def test_invalid_input_never_reaches_the_handler() -> None:
    called = False

    async def spy_handler(data: BaseModel) -> BaseModel:
        nonlocal called
        called = True
        return EchoOutput(message="unreachable")

    contract = make_echo_capability("test.spy").contract
    capability = RegisteredCapability(
        contract=contract, input_model=EchoInput, output_model=EchoOutput, handler=spy_handler
    )
    executor, registry, _ = _executor()
    registry.register(capability)

    with pytest.raises(EchoValidationError):
        await executor.execute("test.spy", {"wrong_field": "no message key"})

    assert (
        called is False
    ), "the handler (standing in for a provider) must never run on invalid input"


async def test_missing_permission_blocks_execution() -> None:
    executor, registry, _ = _executor()
    registry.register(make_permission_gated_capability())

    with pytest.raises(AuthorizationError):
        await executor.execute("test.gated", {"message": "hello"})


async def test_granted_permission_allows_execution() -> None:
    executor, registry, _ = _executor()
    registry.register(make_permission_gated_capability())
    granted = frozenset({Permission(resource="test.resource", action=PermissionAction.READ)})

    result = await executor.execute("test.gated", {"message": "hello"}, granted_permissions=granted)
    assert isinstance(result, EchoOutput)


async def test_write_capability_cannot_execute_before_approval_engine() -> None:
    executor, registry, _ = _executor()
    registry.register(make_write_capability())

    with pytest.raises(WriteCapabilityNotExecutableError):
        await executor.execute("test.write", {"message": "hello"})


async def test_timeout_is_normalized_to_echo_timeout_error() -> None:
    executor, registry, _ = _executor()
    registry.register(make_slow_capability(delay_seconds=0.5, timeout_seconds=0))

    with pytest.raises(EchoTimeoutError):
        await executor.execute("test.slow", {"message": "hello"})


async def test_unexpected_handler_error_is_normalized() -> None:
    executor, registry, _ = _executor()
    registry.register(make_failing_capability())

    with pytest.raises(UnexpectedError):
        await executor.execute("test.failing", {"message": "hello"})


async def test_every_execution_attempt_is_audited_including_failures() -> None:
    executor, registry, tool_calls = _executor()
    registry.register(make_echo_capability())
    registry.register(make_failing_capability())

    await executor.execute("test.echo", {"message": "hello"})
    with pytest.raises(UnexpectedError):
        await executor.execute("test.failing", {"message": "hello"})

    assert len(tool_calls.recorded) == 2
    assert tool_calls.recorded[0]["status"] == "success"
    assert tool_calls.recorded[1]["status"] == "failure"
    assert tool_calls.recorded[1]["error_code"] == "unexpected_error"


async def test_audit_record_carries_correlation_id() -> None:
    executor, registry, tool_calls = _executor()
    registry.register(make_echo_capability())

    await executor.execute("test.echo", {"message": "hi"}, correlation_id="corr_exec_test")

    assert tool_calls.recorded[0]["correlation_id"] == "corr_exec_test"
