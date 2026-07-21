from __future__ import annotations

from providers.models.contracts import ModelRequest, ModelResponse, Provider


class FakeModelAdapter:
    def __init__(self, *, output: str, provider: Provider, model_name: str = "fake-model") -> None:
        self.output = output
        self.provider = provider
        self.model_name = model_name
        self.calls: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(
            output=self.output,
            provider=self.provider,
            model_name=self.model_name,
            latency_ms=1.0,
        )
