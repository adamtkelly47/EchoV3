from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel

from providers.models.contracts import ModelRequest, ModelResponse, Provider

OutputT = TypeVar("OutputT", bound=BaseModel)


class FakeModelGateway:
    """Configurable stand-in for ModelGatewayPort. `generate` echoes the
    prompt it was given by default, so tests can inspect exactly what
    evidence the orchestrator injected — proving the model is given the
    real time rather than asked to recall it from nowhere."""

    def __init__(self, *, structured_decision: BaseModel | None = None) -> None:
        self.structured_decision = structured_decision
        self.generate_calls: list[ModelRequest] = []
        self.structured_calls: list[ModelRequest] = []

    async def generate(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> ModelResponse:
        self.generate_calls.append(request)
        return ModelResponse(
            output=request.prompt, provider=Provider.OLLAMA, model_name="fake", latency_ms=1.0
        )

    async def generate_stream(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> AsyncIterator[str]:
        for word in request.prompt.split(" "):
            yield word + " "

    async def generate_structured(
        self,
        request: ModelRequest,
        output_model: type[OutputT],
        *,
        provider: Provider | None = None,
    ) -> OutputT:
        self.structured_calls.append(request)
        assert self.structured_decision is not None, "configure structured_decision before calling"
        assert isinstance(self.structured_decision, output_model)
        return self.structured_decision
