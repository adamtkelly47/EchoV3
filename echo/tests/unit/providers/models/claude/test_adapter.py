"""No live Claude API key is available in this environment, so this test
mocks the anthropic SDK's own client rather than making a real call —
proves the adapter's translation logic (SDK response -> ModelResponse,
SDK error -> ProviderUnavailableError) without needing live credentials.
Live verification is a documented gap — see Docs/DECISION_LOG.md's Phase 7
entry.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import pytest
from anthropic.types import TextBlock

from core.errors import ProviderUnavailableError
from core.time import FakeClock
from providers.models.claude.adapter import ClaudeAdapter
from providers.models.contracts import ModelRequest, Provider, TaskType


def _fake_message(text: str, input_tokens: int, output_tokens: int) -> SimpleNamespace:
    # A real TextBlock (not a stand-in) — the adapter now type-narrows with
    # isinstance(block, TextBlock), which a SimpleNamespace can't satisfy.
    return SimpleNamespace(
        content=[TextBlock(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


async def test_generate_translates_sdk_response_to_model_response() -> None:
    adapter = ClaudeAdapter(api_key="fake-key", model_name="claude-sonnet-5", clock=FakeClock())
    adapter._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        return_value=_fake_message("hello there", input_tokens=10, output_tokens=5)
    )

    response = await adapter.generate(ModelRequest(task_type=TaskType.CONVERSATION, prompt="hi"))

    assert response.output == "hello there"
    assert response.provider == Provider.CLAUDE
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.cost_estimate_usd is not None and response.cost_estimate_usd > 0
    # the raw SDK object never appears on the response — only plain fields
    assert isinstance(response.output, str)


async def test_sdk_error_is_normalized_to_provider_unavailable() -> None:
    adapter = ClaudeAdapter(api_key="fake-key", model_name="claude-sonnet-5", clock=FakeClock())
    adapter._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.APIConnectionError(request=AsyncMock())
    )

    with pytest.raises(ProviderUnavailableError):
        await adapter.generate(ModelRequest(task_type=TaskType.CONVERSATION, prompt="hi"))
