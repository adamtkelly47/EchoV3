from datetime import UTC, datetime

from pydantic import BaseModel

from core.events import EventEnvelope


class _ExamplePayload(BaseModel):
    account_id: str
    total_value: float


def test_envelope_wraps_a_typed_payload() -> None:
    envelope = EventEnvelope[_ExamplePayload](
        event_type="PortfolioSnapshotCreated",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload=_ExamplePayload(account_id="acc_1", total_value=1000.0),
    )
    assert envelope.payload.account_id == "acc_1"
    assert envelope.event_version == 1  # default


def test_envelope_round_trips_through_json() -> None:
    envelope = EventEnvelope[_ExamplePayload](
        event_type="PortfolioSnapshotCreated",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        correlation_id="corr_1",
        payload=_ExamplePayload(account_id="acc_1", total_value=1000.0),
    )
    restored = EventEnvelope[_ExamplePayload].model_validate_json(envelope.model_dump_json())
    assert restored == envelope


def test_envelope_ids_are_unique_per_instance() -> None:
    payload = _ExamplePayload(account_id="acc_1", total_value=1000.0)
    first = EventEnvelope[_ExamplePayload](
        event_type="PortfolioSnapshotCreated",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload=payload,
    )
    second = EventEnvelope[_ExamplePayload](
        event_type="PortfolioSnapshotCreated",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload=payload,
    )
    assert first.event_id != second.event_id
