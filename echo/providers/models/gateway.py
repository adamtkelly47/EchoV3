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
from core.observability.correlation import get_correlation_id
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


class ModelCallRecorderPort(Protocol):
    """Matches `infrastructure/database/repositories/observability.py`'s
    `ModelCallRecorderPort` structurally — redeclared here rather than
    imported so `providers/` never imports `infrastructure/database/`
    directly (the concrete recorder is wired in at the Application layer,
    `application/model_gateway_factory.py`, matching every other
    provider-factory precedent in this codebase)."""

    async def record(
        self,
        *,
        provider: str,
        model_name: str,
        task_type: str,
        correlation_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: float | None = None,
        cost_estimate_usd: float | None = None,
        escalated: bool = False,
        escalation_reason: str | None = None,
        schema_valid: bool | None = None,
    ) -> str: ...


class ModelGateway:
    def __init__(
        self,
        claude: ModelAdapter,
        ollama: ModelAdapter,
        default_provider: Provider,
        recorder: ModelCallRecorderPort | None = None,
    ) -> None:
        self._adapters: dict[Provider, ModelAdapter] = {
            Provider.CLAUDE: claude,
            Provider.OLLAMA: ollama,
        }
        self._default_provider = default_provider
        self._recorder = recorder

    async def generate(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> ModelResponse:
        """Provider selection is configuration, not a model call itself —
        this is the one place "which provider" is decided. Switching
        providers is a config change (`default_provider`/env var), never a
        code change (Phase 7 verification: "application can switch
        providers through configuration")."""
        response = await self._raw_generate(request, provider)
        await self._record(request, response, provider, schema_valid=None)
        return response

    async def generate_stream(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> AsyncIterator[str]:
        """Not instrumented for Phase 25's model-call telemetry — the
        `StreamingModelAdapter` contract yields raw text chunks with no
        final `ModelResponse` (tokens/latency/cost), and adding that would
        change the streaming contract itself, out of scope for an
        evaluation/observability phase. A real, documented gap (Docs/
        DECISION_LOG.md's Phase 25 entry), not a silent omission."""
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
        response = await self._raw_generate(request, provider)
        try:
            result = output_model.model_validate_json(_extract_json_object(response.output))
        except (PydanticValidationError, ValueError) as exc:
            await self._record(request, response, provider, schema_valid=False)
            raise ModelOutputInvalidError(
                f"model output did not match {output_model.__name__}", detail=str(exc)
            ) from exc
        await self._record(request, response, provider, schema_valid=True)
        return result

    async def _raw_generate(
        self, request: ModelRequest, provider: Provider | None
    ) -> ModelResponse:
        adapter = self._adapters[provider or self._default_provider]
        return await adapter.generate(request)

    async def _record(
        self,
        request: ModelRequest,
        response: ModelResponse,
        explicit_provider: Provider | None,
        *,
        schema_valid: bool | None,
    ) -> None:
        if self._recorder is None:
            return
        # PROMPT.md Phase 25's "Claude escalation rate": an explicit
        # provider override away from the configured default is the one
        # real signal of escalation this codebase has today (e.g.
        # application/orchestrators/insider_intelligence.py's/
        # news_intelligence.py's interpretation steps, which always force
        # Provider.CLAUDE regardless of a local-first default). If the
        # configured default is already Claude, nothing is "escalating"
        # away from local, so this is correctly False in that case too.
        escalated = explicit_provider is not None and explicit_provider != self._default_provider
        await self._recorder.record(
            provider=response.provider.value,
            model_name=response.model_name,
            task_type=request.task_type.value,
            correlation_id=get_correlation_id(),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
            cost_estimate_usd=response.cost_estimate_usd,
            escalated=escalated,
            escalation_reason="explicit provider override" if escalated else None,
            schema_valid=schema_valid,
        )


def _extract_json_object(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return text[start : end + 1]
