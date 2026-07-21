from datetime import UTC, datetime

from pydantic import BaseModel

from core.jobs import FailureClassification, JobEnvelope, RetryPolicy


class _ExampleInput(BaseModel):
    account_id: str


def test_job_envelope_default_retry_policy() -> None:
    job = JobEnvelope[_ExampleInput](
        job_type="portfolio.snapshot",
        input=_ExampleInput(account_id="acc_1"),
        idempotency_key="acc_1-2026-01-01",
        timeout_seconds=30,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert job.retry_policy.max_attempts == 3
    assert job.job_version == 1


def test_job_envelope_round_trips_through_json() -> None:
    job = JobEnvelope[_ExampleInput](
        job_type="portfolio.snapshot",
        input=_ExampleInput(account_id="acc_1"),
        idempotency_key="acc_1-2026-01-01",
        retry_policy=RetryPolicy(max_attempts=5),
        timeout_seconds=30,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    restored = JobEnvelope[_ExampleInput].model_validate_json(job.model_dump_json())
    assert restored == job
    assert restored.retry_policy.max_attempts == 5


def test_failure_classification_values() -> None:
    assert {c.value for c in FailureClassification} == {"transient", "permanent", "unknown"}
