"""The first real capability (PROMPT.md Phase 8: "Current time read
capability"). Lives under application/capabilities/ per CONSTITUTION.md's
Application Structure ("capabilities/ — Expose executable platform
capabilities") rather than any single domain, since "what time is it" is
platform utility, not a business concept owned by Portfolio/Calendar/etc.
Wraps core.time.Clock — never calls datetime.now() itself.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.capabilities import CapabilityContract, ExecutionEnvironment, ReadWriteClassification
from core.time import Clock
from domains.capabilities.models import RegisteredCapability

CAPABILITY_ID = "system.current_time"


class CurrentTimeInput(BaseModel):
    pass


class CurrentTimeOutput(BaseModel):
    iso_timestamp: str
    source: str = "system_clock"


def build_current_time_capability(clock: Clock) -> RegisteredCapability:
    async def handler(data: BaseModel) -> BaseModel:
        return CurrentTimeOutput(iso_timestamp=clock.now_utc().isoformat())

    contract = CapabilityContract(
        capability_id=CAPABILITY_ID,
        version=1,
        display_name="Current time",
        description="Returns the current UTC time from the platform clock.",
        owner="System",
        input_schema=CurrentTimeInput.model_json_schema(),
        output_schema=CurrentTimeOutput.model_json_schema(),
        permission_requirements=[],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=5,
        idempotency_behavior="not applicable — read only, value changes each call by design",
        provenance_requirements="source=system_clock; the response IS the provenance record",
        supported_interfaces=["chat", "api"],
        expected_errors=[],
    )
    return RegisteredCapability(
        contract=contract,
        input_model=CurrentTimeInput,
        output_model=CurrentTimeOutput,
        handler=handler,
    )
