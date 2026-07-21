"""The single model gateway (ADR_0004): application code calls this, never
the Claude or Ollama SDKs directly. Which adapter runs is decided by
configuration (Docs/MODEL_ROUTING.md) or the escalation policy — never by
prompt wording, and never by the model choosing for itself
(CONSTITUTION.md: Capability Planner).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from core.errors import ExecutionError, ModelOutputInvalidError
from providers.models.contracts import ModelRequest, ModelResponse, Provider

OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelAdapter(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


class StreamingModelAdapter(Protocol):
    """Not every adapter supports streaming (Claude doesn't yet — see
    Docs/DECISION_LOG.md's Phase 8 entry) — `ModelGateway.generate_stream`
    checks for this at the call site rather than assuming every adapter
    has it."""

    def generate_stream(self, request: ModelRequest) -> AsyncIterator[str]: ...


class ModelGateway:
    def __init__(
        self, claude: ModelAdapter, ollama: ModelAdapter, default_provider: Provider
    ) -> None:
        self._adapters: dict[Provider, ModelAdapter] = {
            Provider.CLAUDE: claude,
            Provider.OLLAMA: ollama,
        }
        self._default_provider = default_provider

    async def generate(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> ModelResponse:
        """Provider selection is configuration, not a model call itself —
        this is the one place "which provider" is decided. Switching
        providers is a config change (`default_provider`/env var), never a
        code change (Phase 7 verification: "application can switch
        providers through configuration")."""
        adapter = self._adapters[provider or self._default_provider]
        return await adapter.generate(request)

    async def generate_stream(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> AsyncIterator[str]:
        selected = provider or self._default_provider
        adapter = self._adapters[selected]
        if not hasattr(adapter, "generate_stream"):
            raise ExecutionError(f"the {selected.value} adapter does not support streaming")
        async for chunk in adapter.generate_stream(request):
            yield chunk

    async def generate_structured(
        self,
        request: ModelRequest,
        output_model: type[OutputT],
        *,
        provider: Provider | None = None,
    ) -> OutputT:
        """Validates the model's raw output against `output_model` before
        returning it — invalid structured output is rejected here, never
        silently coerced (CONSTITUTION.md: "Structured model output SHALL
        be schema validated before use."). Smaller/local models often wrap
        JSON in prose despite being asked not to — the JSON object is
        extracted from the response before validation, but validation
        itself stays strict; extraction failures still raise."""
        response = await self.generate(request, provider=provider)
        try:
            return output_model.model_validate_json(_extract_json_object(response.output))
        except (PydanticValidationError, ValueError) as exc:
            raise ModelOutputInvalidError(
                f"model output did not match {output_model.__name__}", detail=str(exc)
            ) from exc


def _extract_json_object(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return text[start : end + 1]
