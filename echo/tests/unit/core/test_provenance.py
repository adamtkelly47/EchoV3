from datetime import UTC, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.provenance import ComputedValueRecord, SourceRecord, ValidationStatus


def test_source_record_ids_are_unique_per_instance() -> None:
    kwargs = dict(
        source_type="brokerage-api",
        provider="schwab",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        origin="/v1/accounts",
        parser_version="1",
        validation_status=ValidationStatus.PASSED,
    )
    first = SourceRecord(**kwargs)
    second = SourceRecord(**kwargs)
    assert first.record_id != second.record_id


def test_source_record_round_trips_through_json() -> None:
    record = SourceRecord(
        source_type="brokerage-api",
        provider="schwab",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        origin="/v1/accounts",
        parser_version="1",
        validation_status=ValidationStatus.PASSED,
    )
    restored = SourceRecord.model_validate_json(record.model_dump_json())
    assert restored == record


def test_source_record_is_immutable() -> None:
    record = SourceRecord(
        source_type="brokerage-api",
        provider="schwab",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        origin="/v1/accounts",
        parser_version="1",
        validation_status=ValidationStatus.PASSED,
    )
    with pytest.raises(PydanticValidationError):
        record.provider = "fidelity"  # type: ignore[misc]


def test_computed_value_record_captures_input_lineage() -> None:
    source = SourceRecord(
        source_type="brokerage-api",
        provider="schwab",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        origin="/v1/accounts",
        parser_version="1",
        validation_status=ValidationStatus.PASSED,
    )
    computed = ComputedValueRecord(
        calculation_name="portfolio.total_market_value",
        calculation_version="1",
        input_record_ids=[source.record_id],
        executed_at=datetime(2026, 1, 1, tzinfo=UTC),
        output=12345.67,
        validation_result=ValidationStatus.PASSED,
    )
    assert computed.input_record_ids == [source.record_id]
    restored = ComputedValueRecord.model_validate_json(computed.model_dump_json())
    assert restored == computed
