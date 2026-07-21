"""The single model gateway (ADR_0004): application code calls this, never
the Claude or Ollama SDKs directly. Which adapter runs is decided by
configuration (Docs/MODEL_ROUTING.md) or the escalation policy — never by
prompt wording, and never by the model choosing for itself
(CONSTITUTION.md: Capability Planner).
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from core.errors import ModelOutputInvalidError
from providers.models.contracts import ModelRequest, ModelResponse, Provider

OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelAdapter(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


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
        be schema validated before use.")."""
        response = await self.generate(request, provider=provider)
        try:
            return output_model.model_validate_json(response.output)
        except PydanticValidationError as exc:
            raise ModelOutputInvalidError(
                f"model output did not match {output_model.__name__}", detail=str(exc)
            ) from exc
