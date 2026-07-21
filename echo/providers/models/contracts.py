"""The common request/response schema every model adapter speaks
(Docs/MODEL_ROUTING.md: "A single gateway exposes one common request/
response schema to the rest of the application."). Provider SDK objects
(anthropic's `Message`, Ollama's raw JSON) are translated into this shape
inside each adapter and never escape it (CONSTITUTION.md: Provider SDK
Leakage).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from core.provenance import ValidationStatus


class TaskType(str, Enum):
    """Matches Docs/MODEL_ROUTING.md's workload categories at a coarse
    grain — fine enough to drive the escalation policy, not an exhaustive
    catalog of every possible task."""

    CONVERSATION = "conversation"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    SUMMARIZATION = "summarization"
    SYNTHESIS = "synthesis"


class Provider(str, Enum):
    CLAUDE = "claude"
    OLLAMA = "ollama"


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_type: TaskType
    prompt: str
    context: dict[str, Any] = {}
    timeout_seconds: int = 30
    max_tokens: int | None = None
    temperature: float | None = None


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    output: str
    provider: Provider
    model_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float
    cost_estimate_usd: float | None = None
    validation_status: ValidationStatus = ValidationStatus.PASSED
