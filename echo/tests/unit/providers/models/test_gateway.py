import pytest
from pydantic import BaseModel

from core.errors import ModelOutputInvalidError
from providers.models.contracts import ModelRequest, Provider, TaskType
from providers.models.gateway import ModelGateway
from tests.unit.providers.models.fakes import FakeModelAdapter, FakeModelCallRecorder


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


async def test_json_wrapped_in_prose_is_still_extracted_and_validated() -> None:
    """Small/local models often ignore "reply with only JSON" — the object
    is extracted from surrounding prose rather than requiring a pure-JSON
    response, without weakening the actual schema validation."""
    gateway, _, _ = _gateway(
        ollama_output='Sure, here is the answer: {"label": "positive", "confidence": 0.9}'
    )
    result = await gateway.generate_structured(
        ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
    )
    assert result.label == "positive"


async def test_prose_with_invalid_json_inside_is_still_rejected() -> None:
    gateway, _, _ = _gateway(ollama_output='I think the answer is {"label": "positive"} probably')
    with pytest.raises(ModelOutputInvalidError):
        await gateway.generate_structured(
            ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
        )


async def test_generate_records_a_model_call_with_no_recorder_configured_is_a_noop() -> None:
    """PROMPT.md Phase 25's model-call telemetry is additive — a gateway
    with no recorder configured (e.g. every pre-Phase-25 test fixture)
    must keep working exactly as before."""
    gateway, _, _ = _gateway()
    await gateway.generate(ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"))


async def test_generate_records_a_model_call_when_a_recorder_is_configured() -> None:
    claude = FakeModelAdapter(output="c", provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(output="o", provider=Provider.OLLAMA)
    recorder = FakeModelCallRecorder()
    gateway = ModelGateway(
        claude=claude, ollama=ollama, default_provider=Provider.OLLAMA, recorder=recorder
    )
    await gateway.generate(ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"))
    assert len(recorder.recorded) == 1
    assert recorder.recorded[0]["provider"] == "ollama"
    assert recorder.recorded[0]["task_type"] == "classification"
    assert recorder.recorded[0]["schema_valid"] is None


async def test_explicit_provider_override_away_from_default_is_recorded_as_escalated() -> None:
    """PROMPT.md Phase 25's "Claude escalation rate" — an explicit
    override away from the configured default is the one real escalation
    signal this codebase has (application/orchestrators/insider_
    intelligence.py's/news_intelligence.py's interpretation steps)."""
    claude = FakeModelAdapter(output="c", provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(output="o", provider=Provider.OLLAMA)
    recorder = FakeModelCallRecorder()
    gateway = ModelGateway(
        claude=claude, ollama=ollama, default_provider=Provider.OLLAMA, recorder=recorder
    )
    await gateway.generate(
        ModelRequest(task_type=TaskType.SYNTHESIS, prompt="x"), provider=Provider.CLAUDE
    )
    assert recorder.recorded[0]["escalated"] is True
    assert recorder.recorded[0]["escalation_reason"] is not None


async def test_calling_the_default_provider_explicitly_is_not_an_escalation() -> None:
    claude = FakeModelAdapter(output="c", provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(output="o", provider=Provider.OLLAMA)
    recorder = FakeModelCallRecorder()
    gateway = ModelGateway(
        claude=claude, ollama=ollama, default_provider=Provider.OLLAMA, recorder=recorder
    )
    await gateway.generate(
        ModelRequest(task_type=TaskType.SYNTHESIS, prompt="x"), provider=Provider.OLLAMA
    )
    assert recorder.recorded[0]["escalated"] is False


async def test_generate_structured_records_schema_valid_true_on_success() -> None:
    claude = FakeModelAdapter(output="c", provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(
        output='{"label": "positive", "confidence": 0.9}', provider=Provider.OLLAMA
    )
    recorder = FakeModelCallRecorder()
    gateway = ModelGateway(
        claude=claude, ollama=ollama, default_provider=Provider.OLLAMA, recorder=recorder
    )
    await gateway.generate_structured(
        ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
    )
    assert len(recorder.recorded) == 1
    assert recorder.recorded[0]["schema_valid"] is True


async def test_generate_structured_records_schema_valid_false_on_validation_failure() -> None:
    claude = FakeModelAdapter(output="c", provider=Provider.CLAUDE)
    ollama = FakeModelAdapter(output="not json at all", provider=Provider.OLLAMA)
    recorder = FakeModelCallRecorder()
    gateway = ModelGateway(
        claude=claude, ollama=ollama, default_provider=Provider.OLLAMA, recorder=recorder
    )
    with pytest.raises(ModelOutputInvalidError):
        await gateway.generate_structured(
            ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="x"), _Structured
        )
    assert len(recorder.recorded) == 1
    assert recorder.recorded[0]["schema_valid"] is False
