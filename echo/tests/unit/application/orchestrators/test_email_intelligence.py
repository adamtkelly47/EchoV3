"""Uses a real EmailService backed by fakes (matching
tests/unit/application/orchestrators/test_calendar_writes.py's own
pattern) — proves the orchestrator's wiring against real Email domain
state, not a re-implementation of it.
"""

from datetime import UTC, datetime

from application.orchestrators.email_intelligence import EmailIntelligenceOrchestrator
from core.errors import ModelOutputInvalidError
from core.time import FakeClock
from domains.email.models import EmailCategory
from domains.email.service import EmailService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.application.orchestrators.fakes import FakeEmailModelGateway
from tests.unit.domains.email.fakes import (
    FakeAuditRepository,
    FakeEmailCredentialRepository,
    FakeEmailMessageRepository,
    FakeEmailProvider,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _service(
    clock: FakeClock, provider: FakeEmailProvider
) -> tuple[EmailService, FakeEmailMessageRepository]:
    messages_repo = FakeEmailMessageRepository()
    service = EmailService(
        FakeEmailCredentialRepository(),
        messages_repo,
        provider,
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        clock,
        "state-secret",
    )
    return service, messages_repo


def _raw_message(
    message_id: str, *, subject: str = "Please review", snippet: str = "Can you take a look?"
) -> dict:
    return {
        "id": message_id,
        "threadId": "thread-1",
        "snippet": snippet,
        "labelIds": ["INBOX"],
        "internalDate": "1767268800000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": "alice@example.com"},
            ],
            "parts": [],
        },
    }


async def test_classify_message_persists_and_returns_result() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = FakeEmailProvider()
    provider.get_message_response = _raw_message("msg-1")
    email, messages_repo = _service(clock, provider)
    await email.connect("user_1", "code")

    gateway = FakeEmailModelGateway(
        classification_decisions=[
            {
                "category": EmailCategory.ACTION_NEEDED,
                "needs_response": True,
                "action_items": ["Review the attached document"],
            }
        ]
    )
    orchestrator = EmailIntelligenceOrchestrator(email, gateway, clock)

    classification = await orchestrator.classify_message("user_1", provider_message_id="msg-1")

    assert classification.category == EmailCategory.ACTION_NEEDED
    assert classification.needs_response is True
    assert classification.action_items == ["Review the attached document"]

    stored = await messages_repo.get("user_1", "msg-1")
    assert stored is not None
    assert stored.classification is not None
    assert stored.classification.category == EmailCategory.ACTION_NEEDED


async def test_classify_message_fails_safe_on_model_error() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = FakeEmailProvider()
    provider.get_message_response = _raw_message("msg-2")
    email, _ = _service(clock, provider)
    await email.connect("user_1", "code")

    gateway = FakeEmailModelGateway(raise_on_classify=ModelOutputInvalidError("bad output"))
    orchestrator = EmailIntelligenceOrchestrator(email, gateway, clock)

    classification = await orchestrator.classify_message("user_1", provider_message_id="msg-2")

    assert classification.category == EmailCategory.OTHER
    assert classification.needs_response is False
    assert classification.action_items == []


async def test_summarize_thread_uses_all_messages() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = FakeEmailProvider()
    provider.get_thread_response = {
        "messages": [_raw_message("msg-1"), _raw_message("msg-2", subject="Re: Please review")]
    }
    email, _ = _service(clock, provider)
    await email.connect("user_1", "code")

    gateway = FakeEmailModelGateway(summary_decisions=["Alice asked for a document review."])
    orchestrator = EmailIntelligenceOrchestrator(email, gateway, clock)

    summary = await orchestrator.summarize_thread("user_1", thread_id="thread-1")

    assert summary == "Alice asked for a document review."


async def test_summarize_thread_with_no_messages_does_not_call_model() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = FakeEmailProvider()
    provider.get_thread_response = {"messages": []}
    email, _ = _service(clock, provider)
    await email.connect("user_1", "code")

    gateway = FakeEmailModelGateway()
    orchestrator = EmailIntelligenceOrchestrator(email, gateway, clock)

    summary = await orchestrator.summarize_thread("user_1", thread_id="empty-thread")

    assert "No messages found" in summary
    assert len(gateway.structured_calls) == 0
