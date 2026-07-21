"""Live test against the real Ollama container (already running in the
Compose stack) — not mocked, unlike the Claude adapter tests, since Ollama
requires no API key and is already part of the local environment. Requires
the tiny model in core.config.Settings.ollama_model_name to be pulled
first (see Docs/OPERATIONS.md's Ollama Models section) — skips gracefully
if it isn't, the same way tests/integration/conftest.py skips when
DATABASE_URL is unset.
"""

import httpx
import pytest

from core.config import get_settings
from core.time import SystemClock
from providers.models.contracts import ModelRequest, Provider, TaskType
from providers.models.ollama.adapter import OllamaAdapter


async def _model_is_pulled(base_url: str, model_name: str) -> bool:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{base_url}/api/tags")
        response.raise_for_status()
        models = {m["name"] for m in response.json().get("models", [])}
    return model_name in models


async def test_generate_against_real_ollama() -> None:
    settings = get_settings()
    if not await _model_is_pulled(settings.ollama_base_url, settings.ollama_model_name):
        pytest.skip(
            f"{settings.ollama_model_name} is not pulled — "
            f"see Docs/OPERATIONS.md's Ollama Models section"
        )

    adapter = OllamaAdapter(settings.ollama_base_url, settings.ollama_model_name, SystemClock())
    response = await adapter.generate(
        ModelRequest(
            task_type=TaskType.CONVERSATION,
            prompt="Reply with exactly the word: pong",
            max_tokens=10,
            timeout_seconds=30,
        )
    )

    assert response.provider == Provider.OLLAMA
    assert response.model_name == settings.ollama_model_name
    assert isinstance(response.output, str) and len(response.output) > 0
    assert response.latency_ms > 0
    assert response.cost_estimate_usd == 0.0
