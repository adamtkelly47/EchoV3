from datetime import UTC, datetime

import pytest

from core.errors import ProviderUnavailableError
from core.time import FakeClock
from domains.calendar.errors import (
    CalendarCredentialNotFoundError,
    CalendarOAuthStateInvalidError,
    CalendarTokenRefreshError,
)
from domains.calendar.service import CalendarService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.calendar.fakes import (
    FakeAuditRepository,
    FakeCalendarCredentialRepository,
    FakeCalendarEventRepository,
    FakeCalendarProvider,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _service(
    *, clock: FakeClock | None = None, provider: FakeCalendarProvider | None = None
) -> tuple[CalendarService, FakeCalendarProvider, FakeCalendarCredentialRepository]:
    credentials = FakeCalendarCredentialRepository()
    events = FakeCalendarEventRepository()
    provider = provider or FakeCalendarProvider()
    cipher = SecretCipher(_FERNET_KEY)
    audit = FakeAuditRepository()
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service = CalendarService(credentials, events, provider, cipher, audit, clock, "state-secret")
    return service, provider, credentials


async def test_is_connected_reflects_credential_presence() -> None:
    """PROMPT.md Phase 22 implement item 6: "integration status.\" """
    service, _, _ = _service()
    assert await service.is_connected("user_1") is False

    await service.connect("user_1", "auth-code-123")
    assert await service.is_connected("user_1") is True


async def test_connect_stores_encrypted_tokens_not_plaintext() -> None:
    service, _, credentials = _service()
    credential = await service.connect("user_1", "auth-code-123")

    assert credential.encrypted_access_token != "fake-access-token"
    assert credential.encrypted_refresh_token != "fake-refresh-token"
    stored = await credentials.get_for_user("user_1")
    assert stored is not None
    assert stored.scope == "https://www.googleapis.com/auth/calendar.readonly"


async def test_start_and_complete_authorization_round_trips_user_id() -> None:
    service, provider, _ = _service()
    url = service.start_authorization("user_1")
    assert "state=" in url

    state = url.split("state=", 1)[1]
    credential = await service.complete_authorization("auth-code-123", state)
    assert credential.user_id == "user_1"


async def test_complete_authorization_rejects_state_for_different_secret() -> None:
    service, _, _ = _service()
    url = service.start_authorization("user_1")
    state = url.split("state=", 1)[1]

    credentials = FakeCalendarCredentialRepository()
    events = FakeCalendarEventRepository()
    other_service = CalendarService(
        credentials,
        events,
        FakeCalendarProvider(),
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
        "different-secret",
    )
    with pytest.raises(CalendarOAuthStateInvalidError):
        await other_service.complete_authorization("auth-code-123", state)


async def test_list_events_calls_provider_when_cache_empty() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.events_response = [
        {
            "id": "event-1",
            "summary": "Standup",
            "start": {"dateTime": "2026-01-02T09:00:00Z"},
            "end": {"dateTime": "2026-01-02T09:15:00Z"},
        }
    ]

    events = await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert len(events) == 1
    assert events[0].summary == "Standup"
    assert any(call[0] == "list_events" for call in provider.calls)


async def test_list_events_second_call_uses_cache_not_provider() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.events_response = [
        {
            "id": "event-1",
            "summary": "Standup",
            "start": {"dateTime": "2026-01-02T09:00:00Z"},
            "end": {"dateTime": "2026-01-02T09:15:00Z"},
        }
    ]

    await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )
    calls_after_first = len(provider.calls)

    await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert len(provider.calls) == calls_after_first  # no new provider calls — served from cache


async def test_list_events_with_query_always_calls_provider() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.events_response = []

    await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )
    calls_after_first = len([c for c in provider.calls if c[0] == "list_events"])

    await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
        query="standup",
    )

    assert len([c for c in provider.calls if c[0] == "list_events"]) == calls_after_first + 1


async def test_list_events_raises_when_no_credential_stored() -> None:
    service, _, _ = _service()
    with pytest.raises(CalendarCredentialNotFoundError):
        await service.list_events(
            "unconnected_user",
            time_min=datetime(2026, 1, 2, tzinfo=UTC),
            time_max=datetime(2026, 1, 3, tzinfo=UTC),
        )


async def test_expired_token_triggers_refresh_and_persists_new_token() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, credentials = _service(clock=clock)
    await service.connect("user_1", "code")  # expires_at = 13:00 (3600s TTL)

    clock.set(datetime(2026, 1, 1, 12, 58, 0, tzinfo=UTC))  # inside the 5-minute refresh buffer
    provider.events_response = []
    await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert any(call[0] == "refresh_access_token" for call in provider.calls)
    stored = await credentials.get_for_user("user_1")
    assert stored is not None
    assert stored.access_token_expires_at == datetime(2026, 1, 1, 13, 58, 0, tzinfo=UTC)


async def test_token_refresh_failure_surfaces_as_calendar_token_refresh_error() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, _ = _service(clock=clock)
    await service.connect("user_1", "code")
    provider.raise_on_refresh = ProviderUnavailableError("Google rejected the refresh token")

    clock.set(datetime(2026, 1, 1, 12, 58, 0, tzinfo=UTC))
    with pytest.raises(CalendarTokenRefreshError):
        await service.list_events(
            "user_1",
            time_min=datetime(2026, 1, 2, tzinfo=UTC),
            time_max=datetime(2026, 1, 3, tzinfo=UTC),
        )


async def test_get_event_uses_cache_when_fresh() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.events_response = [
        {
            "id": "event-1",
            "summary": "Standup",
            "start": {"dateTime": "2026-01-02T09:00:00Z"},
            "end": {"dateTime": "2026-01-02T09:15:00Z"},
        }
    ]
    await service.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )
    calls_before = len([c for c in provider.calls if c[0] == "get_event"])

    event = await service.get_event("user_1", event_id="event-1")

    assert event.summary == "Standup"
    assert (
        len([c for c in provider.calls if c[0] == "get_event"]) == calls_before
    )  # served from cache


async def test_get_event_calls_provider_when_not_cached() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.get_event_response = {
        "id": "event-2",
        "summary": "1:1",
        "start": {"dateTime": "2026-01-02T14:00:00Z"},
        "end": {"dateTime": "2026-01-02T14:30:00Z"},
    }

    event = await service.get_event("user_1", event_id="event-2")

    assert event.summary == "1:1"
    assert any(call[0] == "get_event" for call in provider.calls)


async def test_free_busy_returns_parsed_periods() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.free_busy_response = {
        "calendars": {
            "primary": {"busy": [{"start": "2026-01-02T09:00:00Z", "end": "2026-01-02T10:00:00Z"}]}
        }
    }

    result = await service.free_busy(
        "user_1",
        calendar_ids=["primary"],
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert len(result["primary"]) == 1
    assert result["primary"][0].start == datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC)
