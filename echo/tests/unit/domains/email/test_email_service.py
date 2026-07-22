from datetime import UTC, datetime

import pytest

from core.errors import ProviderUnavailableError
from core.time import FakeClock
from domains.email.errors import (
    EmailCredentialNotFoundError,
    EmailOAuthStateInvalidError,
    EmailTokenRefreshError,
)
from domains.email.service import EmailService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.email.fakes import (
    FakeAuditRepository,
    FakeEmailCredentialRepository,
    FakeEmailMessageRepository,
    FakeEmailProvider,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _service(
    *, clock: FakeClock | None = None, provider: FakeEmailProvider | None = None
) -> tuple[EmailService, FakeEmailProvider, FakeEmailCredentialRepository]:
    credentials = FakeEmailCredentialRepository()
    messages = FakeEmailMessageRepository()
    provider = provider or FakeEmailProvider()
    cipher = SecretCipher(_FERNET_KEY)
    audit = FakeAuditRepository()
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service = EmailService(credentials, messages, provider, cipher, audit, clock, "state-secret")
    return service, provider, credentials


def _raw_message(message_id: str = "msg-1", *, unread: bool = True) -> dict:
    return {
        "id": message_id,
        "threadId": "thread-1",
        "snippet": "hi there",
        "labelIds": ["INBOX"] + (["UNREAD"] if unread else []),
        "internalDate": "1767268800000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "bob@example.com"},
            ],
            "parts": [],
        },
    }


async def test_is_connected_reflects_credential_presence() -> None:
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


async def test_start_and_complete_authorization_round_trips_user_id() -> None:
    service, _, _ = _service()
    url = service.start_authorization("user_1")
    state = url.split("state=", 1)[1]
    credential = await service.complete_authorization("auth-code-123", state)
    assert credential.user_id == "user_1"


async def test_complete_authorization_rejects_state_for_different_secret() -> None:
    service, _, _ = _service()
    url = service.start_authorization("user_1")
    state = url.split("state=", 1)[1]

    other_service = EmailService(
        FakeEmailCredentialRepository(),
        FakeEmailMessageRepository(),
        FakeEmailProvider(),
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
        "different-secret",
    )
    with pytest.raises(EmailOAuthStateInvalidError):
        await other_service.complete_authorization("auth-code-123", state)


async def test_search_messages_calls_provider_when_cache_empty() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.list_messages_response = [_raw_message()]

    messages = await service.search_messages("user_1")

    assert len(messages) == 1
    assert messages[0].subject == "Hello"
    assert any(call[0] == "list_messages" for call in provider.calls)


async def test_search_messages_second_call_uses_cache() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.list_messages_response = [_raw_message()]

    await service.search_messages("user_1")
    calls_after_first = len([c for c in provider.calls if c[0] == "list_messages"])

    await service.search_messages("user_1")

    assert len([c for c in provider.calls if c[0] == "list_messages"]) == calls_after_first


async def test_search_messages_with_query_always_calls_provider() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.list_messages_response = []

    await service.search_messages("user_1")
    await service.search_messages("user_1", query="invoice")

    assert len([c for c in provider.calls if c[0] == "list_messages"]) == 2


async def test_search_messages_raises_when_no_credential_stored() -> None:
    service, _, _ = _service()
    with pytest.raises(EmailCredentialNotFoundError):
        await service.search_messages("unconnected_user")


async def test_expired_token_triggers_refresh_and_persists_new_token() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, credentials = _service(clock=clock)
    await service.connect("user_1", "code")  # expires_at = 13:00 (3600s TTL)

    clock.set(datetime(2026, 1, 1, 12, 58, 0, tzinfo=UTC))
    provider.list_messages_response = []
    await service.search_messages("user_1")

    assert any(call[0] == "refresh_access_token" for call in provider.calls)
    stored = await credentials.get_for_user("user_1")
    assert stored is not None
    assert stored.access_token_expires_at == datetime(2026, 1, 1, 13, 58, 0, tzinfo=UTC)


async def test_token_refresh_failure_surfaces_as_email_token_refresh_error() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, _ = _service(clock=clock)
    await service.connect("user_1", "code")
    provider.raise_on_refresh = ProviderUnavailableError("Google rejected the refresh token")

    clock.set(datetime(2026, 1, 1, 12, 58, 0, tzinfo=UTC))
    with pytest.raises(EmailTokenRefreshError):
        await service.search_messages("user_1")


async def test_get_message_uses_cache_when_fresh() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.list_messages_response = [_raw_message()]
    await service.search_messages("user_1")
    calls_before = len([c for c in provider.calls if c[0] == "get_message"])

    message = await service.get_message("user_1", provider_message_id="msg-1")

    assert message.subject == "Hello"
    assert len([c for c in provider.calls if c[0] == "get_message"]) == calls_before


async def test_get_message_calls_provider_when_not_cached() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.get_message_response = _raw_message("msg-2")

    message = await service.get_message("user_1", provider_message_id="msg-2")

    assert message.provider_message_id == "msg-2"
    assert any(call[0] == "get_message" for call in provider.calls)


async def test_get_thread_parses_all_messages() -> None:
    service, provider, _ = _service()
    await service.connect("user_1", "code")
    provider.get_thread_response = {"messages": [_raw_message("msg-1"), _raw_message("msg-2")]}

    messages = await service.get_thread("user_1", thread_id="thread-1")

    assert len(messages) == 2
    assert {m.provider_message_id for m in messages} == {"msg-1", "msg-2"}


async def test_cache_message_upserts_from_raw() -> None:
    service, _, _ = _service()
    await service.connect("user_1", "code")

    cached = await service.cache_message("user_1", _raw_message("msg-3"))

    assert cached.provider_message_id == "msg-3"
    reloaded = await service.get_message("user_1", provider_message_id="msg-3")
    assert reloaded.provider_message_id == "msg-3"
