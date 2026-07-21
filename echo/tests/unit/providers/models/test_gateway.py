import pytest
from pydantic import BaseModel

from core.errors import ModelOutputInvalidError
from providers.models.contracts import ModelRequest, Provider, TaskType
from providers.models.gateway import ModelGateway
from tests.unit.providers.models.fakes import FakeModelAdapter


class _Structured(BaseModel):
    label: str
    confidence: float


def _gateway(
    claude_output: str = "claude says hi", ollama_output: str = "ollama says hi"
) -> tuple[ModelGateway, FakeModelAdapter, FakeModelAdapter]:
    claude = FakeModelAdapter(output=claude_output, provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(output=ollama_output, provider=Provider.OLLAMA)
    gateway = ModelGateway(claude=claude, ollama=ollama, default_provider=Provider.OLLAMA)
    return gateway, claude, ollama


async def test_default_provider_is_used_when_none_specified() -> None:
    gateway, claude, ollama = _gateway()
    await gateway.generate(ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"))
    assert len(ollama.calls) == 1
    assert len(claude.calls) == 0


async def test_explicit_provider_overrides_default() -> None:
    gateway, claude, ollama = _gateway()
    await gateway.generate(
        ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), provider=Provider.CLAUDE
    )
    assert len(claude.calls) == 1
    assert len(ollama.calls) == 0


async def test_switching_the_default_provider_is_a_construction_time_config_change() -> None:
    """Docs/MODEL_ROUTING.md verification: the application switches
    providers through configuration, not code — proven by constructing two
    gateways from the same adapters with a different default_provider."""
    claude = FakeModelAdapter(output="c", provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(output="o", provider=Provider.OLLAMA)

    ollama_first = ModelGateway(claude=claude, ollama=ollama, default_provider=Provider.OLLAMA)
    claude_first = ModelGateway(claude=claude, ollama=ollama, default_provider=Provider.CLAUDE)

    request = ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x")
    await ollama_first.generate(request)
    await claude_first.generate(request)

    assert len(ollama.calls) == 1
    assert len(claude.calls) == 1


async def test_valid_structured_output_is_returned_as_the_typed_model() -> None:
    gateway, _, _ = _gateway(ollama_output='{"label": "positive", "confidence": 0.9}')
    result = await gateway.generate_structured(
        ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
    )
    assert isinstance(result, _Structured)
    assert result.label == "positive"


async def test_invalid_structured_output_is_rejected_not_coerced() -> None:
    gateway, _, _ = _gateway(ollama_output="not json at all")
    with pytest.raises(ModelOutputInvalidError):
        await gateway.generate_structured(
            ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
        )


async def test_structured_output_missing_required_field_is_rejected() -> None:
    gateway, _, _ = _gateway(ollama_output='{"label": "positive"}')  # missing "confidence"
    with pytest.raises(ModelOutputInvalidError):
        await gateway.generate_structured(
            ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
        )
