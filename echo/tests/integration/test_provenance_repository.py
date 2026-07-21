from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.provenance import ComputedValueRecord, SourceRecord, ValidationStatus
from infrastructure.database.repositories.provenance import (
    PostgresComputedValueRecordRepository,
    PostgresSourceRecordRepository,
)


async def test_source_record_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresSourceRecordRepository(db_session)
    record = SourceRecord(
        source_type="brokerage-api",
        provider="schwab",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        origin="/v1/accounts",
        parser_version="1",
        validation_status=ValidationStatus.PASSED,
    )

    await repo.save(record)
    restored = await repo.get(record.record_id)

    assert restored is not None
    assert restored.record_id == record.record_id
    assert restored.provider == "schwab"
    assert restored.validation_status == ValidationStatus.PASSED


async def test_computed_value_record_preserves_lineage(db_session: AsyncSession) -> None:
    source_repo = PostgresSourceRecordRepository(db_session)
    computed_repo = PostgresComputedValueRecordRepository(db_session)

    source = SourceRecord(
        source_type="brokerage-api",
        provider="schwab",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        origin="/v1/accounts",
        parser_version="1",
        validation_status=ValidationStatus.PASSED,
    )
    await source_repo.save(source)

    computed = ComputedValueRecord(
        calculation_name="portfolio.total_market_value",
        calculation_version="1",
        input_record_ids=[source.record_id],
        executed_at=datetime(2026, 1, 1, tzinfo=UTC),
        output=12345.67,
        validation_result=ValidationStatus.PASSED,
    )
    await computed_repo.save(computed)

    restored = await computed_repo.get(computed.record_id)
    assert restored is not None
    assert restored.input_record_ids == [source.record_id]
    assert restored.output == 12345.67
