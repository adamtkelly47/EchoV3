"""Ollama adapter — local inference, treated as an untrusted candidate
processor (CONSTITUTION.md: "The local model is treated as an untrusted
inference processor... Its outputs must be schema validated."). Ollama's
raw JSON response never leaves this module — see contracts.ModelResponse.
"""

from __future__ import annotations

import httpx

from core.errors import ProviderUnavailableError
from core.time import Clock
from providers.models.contracts import ModelRequest, ModelResponse, Provider


class OllamaAdapter:
    def __init__(self, base_url: str, model_name: str, clock: Clock) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._clock = clock

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start = self._clock.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model_name,
                        "prompt": request.prompt,
                        "stream": False,
                        **(
                            {"options": {"num_predict": request.max_tokens}}
                            if request.max_tokens
                            else {}
                        ),
                    },
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
