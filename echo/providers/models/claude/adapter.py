"""Claude adapter. `anthropic` SDK objects (Message, APIError, ...) never
leave this module — see contracts.ModelResponse (CONSTITUTION.md: Provider
SDK Leakage). Claude must never receive secrets or unrestricted raw system
access (CONSTITUTION.md Section 5.8) — callers are responsible for what
goes into `request.prompt`/`request.context`; this adapter does not add
anything beyond what it's given.
"""

from __future__ import annotations

import anthropic
from anthropic.types import TextBlock

from core.errors import ProviderUnavailableError
from core.time import Clock
from providers.models.claude.pricing import estimate_cost_usd
from providers.models.contracts import ModelRequest, ModelResponse, Provider


class ClaudeAdapter:
    def __init__(self, api_key: str, model_name: str, clock: Clock) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model_name = model_name
        self._clock = clock

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start = self._clock.monotonic()
        try:
            message = await self._client.messages.create(
                model=self._model_name,
                max_tokens=request.max_tokens or 1024,
                messages=[{"role": "user", "content": request.prompt}],
                timeout=request.timeout_seconds,
            )
        except anthropic.APIError as exc:
            raise ProviderUnavailableError(f"Claude request failed: {exc}") from exc

        latency_ms = (self._clock.monotonic() - start) * 1000
        output = "".join(block.text for block in message.content if isinstance(block, TextBlock))
        return ModelResponse(
            output=output,
            provider=Provider.CLAUDE,
            model_name=self._model_name,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
            cost_estimate_usd=estimate_cost_usd(
                self._model_name, message.usage.input_tokens, message.usage.output_tokens
            ),
        )
