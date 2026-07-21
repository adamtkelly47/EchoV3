"""The typed contract every background job must satisfy (PROMPT.md Section
5.3: "A job must have: Job type, Version, Input schema, Idempotency key,
Retry policy, Timeout, Provenance requirements, Output schema, Failure
classification."). The worker (echo/apps/worker) consumes jobs shaped like
this starting Phase 24; the throwaway `echo:jobs:test` string payload from
Phase 1 is replaced once a real job type is introduced.

Deliberately a separate contract from `core/events/envelope.py`: an event
represents a completed business fact, a job represents work still to be
done — CONSTITUTION.md's Event Principles explicitly exclude "intentions"
and "commands" from what an event is allowed to represent, so jobs cannot
reuse the event envelope's semantics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from core.identifiers import new_id

InputT = TypeVar("InputT", bound=BaseModel)


class FailureClassification(str, Enum):
    """Whether a failed job attempt should be retried, per CONSTITUTION.md's
    Retry Philosophy ("Retries should never duplicate write operations
    unless idempotency guarantees exist.")."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0


class JobEnvelope(BaseModel, Generic[InputT]):
    model_config = ConfigDict(frozen=True)

    job_id: str = Field(default_factory=lambda: new_id("job"))
    job_type: str
    job_version: int = 1
    input: InputT
    idempotency_key: str
    retry_policy: RetryPolicy = RetryPolicy()
    timeout_seconds: int
    correlation_id: str | None = None
    created_at: datetime
