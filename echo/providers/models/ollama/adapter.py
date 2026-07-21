"""Ollama adapter — local inference, treated as an untrusted candidate
processor (CONSTITUTION.md: "The local model is treated as an untrusted
inference processor... Its outputs must be schema validated."). Ollama's
raw JSON response never leaves this module — see contracts.ModelResponse.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from core.errors import ProviderUnavailableError
from core.time import Clock
from providers.models.contracts import ModelRequest, ModelResponse, Provider


class OllamaAdapter:
    def __init__(self, base_url: str, model_name: str, clock: Clock) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._clock = clock

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, object]:
        options: dict[str, object] = {}
        if request.max_tokens:
            options["num_predict"] = request.max_tokens
        if request.temperature is not None:
            options["temperature"] = request.temperature
        return {
            "model": self._model_name,
            "prompt": request.prompt,
            "stream": stream,
            **({"options": options} if options else {}),
        }

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start = self._clock.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate", json=self._payload(request, stream=False)
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Ollama request failed: {exc}") from exc

        latency_ms = (self._clock.monotonic() - start) * 1000
        return ModelResponse(
            output=data.get("response", ""),
            provider=Provider.OLLAMA,
            model_name=self._model_name,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            latency_ms=latency_ms,
            cost_estimate_usd=0.0,  # local inference — no per-token API cost
        )

    async def generate_stream(self, request: ModelRequest) -> AsyncIterator[str]:
        """Yields text deltas as they arrive — the streaming half of
        PROMPT.md Phase 8's "Streaming response API." Ollama's `/api/generate`
        with `stream: true` returns newline-delimited JSON objects, each
        carrying one `response` fragment."""
        try:
            async with (
                httpx.AsyncClient(timeout=request.timeout_seconds) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/api/generate",
                    json=self._payload(request, stream=True),
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        yield chunk["response"]
                    if chunk.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Ollama streaming request failed: {exc}") from exc
