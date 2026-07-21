from providers.models.contracts import ModelRequest, ModelResponse, Provider, TaskType


def test_model_request_round_trips_through_json() -> None:
    request = ModelRequest(task_type=TaskType.CLASSIFICATION, prompt="classify this")
    restored = ModelRequest.model_validate_json(request.model_dump_json())
    assert restored == request


def test_model_response_round_trips_through_json() -> None:
    response = ModelResponse(
        output="hello",
        provider=Provider.OLLAMA,
        model_name="llama3.2:1b",
        latency_ms=42.0,
    )
    restored = ModelResponse.model_validate_json(response.model_dump_json())
    assert restored == response


def test_model_request_defaults() -> None:
    request = ModelRequest(task_type=TaskType.CONVERSATION, prompt="hi")
    assert request.timeout_seconds == 30
    assert request.max_tokens is None
    assert request.context == {}
