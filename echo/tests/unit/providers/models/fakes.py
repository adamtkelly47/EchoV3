from __future__ import annotations

from typing import Any

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


class FakeModelCallRecorder:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

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
    ) -> str:
        call_id = f"modelcall_fake_{len(self.recorded)}"
        self.recorded.append(
            {
                "call_id": call_id,
                "provider": provider,
                "model_name": model_name,
                "task_type": task_type,
                "correlation_id": correlation_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "cost_estimate_usd": cost_estimate_usd,
                "escalated": escalated,
                "escalation_reason": escalation_reason,
                "schema_valid": schema_valid,
            }
        )
        return call_id
