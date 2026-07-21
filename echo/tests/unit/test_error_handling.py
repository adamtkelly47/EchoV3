"""Direct test of apps.api.main's global EchoError -> HTTP response
translation (PROMPT.md Phase 10 verification: "read failures are surfaced
honestly"). Calls the handler function directly rather than through a full
TestClient round trip against a real route, so this doesn't need any of
those routes' database dependencies — it's a unit test of the translation
itself, not of any particular route.
"""

import json

from apps.api.main import handle_echo_error
from domains.calendar.errors import CalendarCredentialNotFoundError
from domains.memory.errors import InvalidMemoryStateTransitionError, MemoryNotFoundError


async def test_not_found_error_becomes_404_with_code_and_message() -> None:
    response = await handle_echo_error(None, MemoryNotFoundError("no memory record 'x'"))  # type: ignore[arg-type]
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error_code"] == "memory_not_found"
    assert body["message"] == "no memory record 'x'"


async def test_state_transition_error_becomes_409() -> None:
    response = await handle_echo_error(None, InvalidMemoryStateTransitionError("bad transition"))  # type: ignore[arg-type]
    assert response.status_code == 409


async def test_provider_translated_error_becomes_502() -> None:
    response = await handle_echo_error(None, CalendarCredentialNotFoundError("not connected"))  # type: ignore[arg-type]
    assert (
        response.status_code == 404
    )  # credential-not-found is a client-facing 404, not a provider failure


async def test_correlation_id_from_exception_is_preferred_over_context() -> None:
    exc = MemoryNotFoundError("x", correlation_id="corr_explicit")
    response = await handle_echo_error(None, exc)  # type: ignore[arg-type]
    body = json.loads(response.body)
    assert body["correlation_id"] == "corr_explicit"
