from core.capabilities import CapabilityContract, ExecutionEnvironment, ReadWriteClassification
from core.security.permissions import Permission, PermissionAction


def _example_contract(**overrides: object) -> CapabilityContract:
    defaults: dict[str, object] = dict(
        capability_id="calendar.search_events",
        version=1,
        display_name="Search calendar events",
        description="Search the user's calendar for events matching a query.",
        owner="Calendar",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "array"},
        permission_requirements=[
            Permission(resource="calendar.events", action=PermissionAction.READ)
        ],
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=10,
        idempotency_behavior="not applicable — read only",
        provenance_requirements="attach a SourceRecord per returned event",
        supported_interfaces=["chat", "dashboard", "api"],
        expected_errors=["provider_unavailable", "timeout_error"],
    )
    defaults.update(overrides)
    return CapabilityContract(**defaults)  # type: ignore[arg-type]


def test_read_capability_has_no_approval_requirement_by_default() -> None:
    contract = _example_contract()
    assert contract.approval_requirement is None
    assert contract.read_write_classification == ReadWriteClassification.READ


def test_write_capability_can_declare_an_approval_requirement() -> None:
    contract = _example_contract(
        capability_id="calendar.propose_create_event",
        read_write_classification=ReadWriteClassification.WRITE,
        approval_requirement="calendar.create_event",
    )
    assert contract.read_write_classification == ReadWriteClassification.WRITE
    assert contract.approval_requirement == "calendar.create_event"


def test_contract_round_trips_through_json() -> None:
    contract = _example_contract()
    restored = CapabilityContract.model_validate_json(contract.model_dump_json())
    assert restored == contract
