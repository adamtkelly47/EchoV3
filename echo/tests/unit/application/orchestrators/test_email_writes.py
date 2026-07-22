"""Uses real ApprovalService + real EmailService, both backed by fakes —
matching tests/unit/application/orchestrators/test_calendar_writes.py's
identical pattern: proves the orchestrator's wiring against the actual
Phase 6 state machine, not a re-implementation of it.
"""

from datetime import UTC, datetime, timedelta

import pytest

from application.orchestrators.email_writes import EmailWriteOrchestrator
from core.errors import ApprovalRequiredError, ValidationError
from core.time import FakeClock
from domains.approvals.models import ProposalStatus
from domains.approvals.service import ApprovalService
from domains.email.service import EmailService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.approvals.fakes import (
    FakeApprovalDecisionRepository,
    FakeApprovalProposalRepository,
)
from tests.unit.domains.email.fakes import (
    FakeAuditRepository,
    FakeEmailCredentialRepository,
    FakeEmailMessageRepository,
    FakeEmailProvider,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _orchestrator(
    clock: FakeClock | None = None, provider: FakeEmailProvider | None = None
) -> tuple[
    EmailWriteOrchestrator,
    ApprovalService,
    EmailService,
    FakeEmailProvider,
    FakeEmailMessageRepository,
]:
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = provider or FakeEmailProvider()
    messages_repo = FakeEmailMessageRepository()
    approvals = ApprovalService(
        FakeApprovalProposalRepository(),
        FakeApprovalDecisionRepository(),
        FakeAuditRepository(),
        clock,
    )
    email = EmailService(
        FakeEmailCredentialRepository(),
        messages_repo,
        provider,
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        clock,
        "state-secret",
    )
    orchestrator = EmailWriteOrchestrator(approvals, email, provider)
    return orchestrator, approvals, email, provider, messages_repo


async def _connected(email: EmailService, user_id: str = "user_1") -> None:
    await email.connect(user_id, "auth-code")


async def test_propose_send_message_builds_mime_and_awaits_approval() -> None:
    orchestrator, _, email, _, _ = _orchestrator()
    await _connected(email)

    proposal = await orchestrator.propose_send_message(
        "user_1", to=["bob@example.com"], subject="Hi", body="Hello there"
    )

    assert proposal.status == ProposalStatus.AWAITING_APPROVAL
    assert proposal.payload["action"] == "send_message"
    assert "raw_mime" in proposal.payload


async def test_full_lifecycle_no_send_before_approval() -> None:
    orchestrator, _, _, provider, _ = _orchestrator()

    await orchestrator.propose_send_message(
        "user_1", to=["bob@example.com"], subject="Hi", body="Hello there"
    )

    assert not any(c[0] == "send_message" for c in provider.calls)


async def test_execute_before_approval_is_rejected() -> None:
    orchestrator, _, email, _, _ = _orchestrator()
    await _connected(email)

    proposal = await orchestrator.propose_send_message(
        "user_1", to=["bob@example.com"], subject="Hi", body="Hello there"
    )

    with pytest.raises(ApprovalRequiredError):
        await orchestrator.execute_proposal(proposal.proposal_id, "user_1")


async def test_approved_send_executes_and_verifies_sent_label() -> None:
    orchestrator, approvals, email, provider, _ = _orchestrator()
    await _connected(email)
    provider.send_message_response = {"id": "sent-1", "threadId": "thread-1", "labelIds": ["SENT"]}
    provider.get_message_response = provider.send_message_response

    proposal = await orchestrator.propose_send_message(
        "user_1", to=["bob@example.com"], subject="Hi", body="Hello there"
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    executed = await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert executed.status == ProposalStatus.EXECUTED


async def test_duplicate_execution_does_not_send_twice() -> None:
    orchestrator, approvals, email, provider, _ = _orchestrator()
    await _connected(email)
    provider.send_message_response = {"id": "sent-1", "threadId": "thread-1", "labelIds": ["SENT"]}
    provider.get_message_response = provider.send_message_response

    proposal = await orchestrator.propose_send_message(
        "user_1", to=["bob@example.com"], subject="Hi", body="Hello there"
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))

    await orchestrator.execute_proposal(proposal.proposal_id, "user_1")
    await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert len([c for c in provider.calls if c[0] == "send_message"]) == 1


async def test_propose_reply_uses_original_message_thread_and_message_id() -> None:
    orchestrator, _, email, provider, _ = _orchestrator()
    await _connected(email)
    provider.get_message_response = {
        "id": "orig-1",
        "threadId": "thread-42",
        "labelIds": [],
        "internalDate": "1767268800000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Question"},
                {"name": "From", "value": "alice@example.com"},
                {"name": "Message-ID", "value": "<orig@mail.gmail.com>"},
            ],
            "parts": [],
        },
    }

    proposal = await orchestrator.propose_reply(
        "user_1", provider_message_id="orig-1", body="Sure, sounds good"
    )

    assert proposal.payload["thread_id"] == "thread-42"
    assert proposal.summary.startswith("Reply to alice@example.com")


async def test_propose_label_requires_at_least_one_change() -> None:
    orchestrator, _, email, _, _ = _orchestrator()
    await _connected(email)

    with pytest.raises(ValidationError):
        await orchestrator.propose_label("user_1", provider_message_id="msg-1")


async def test_approved_archive_executes_and_caches_result() -> None:
    orchestrator, approvals, email, provider, _ = _orchestrator()
    await _connected(email)
    provider.modify_labels_response = {"id": "msg-1", "labelIds": ["UNREAD"]}
    provider.get_message_response = {"id": "msg-1", "labelIds": ["UNREAD"]}

    proposal = await orchestrator.propose_archive("user_1", provider_message_id="msg-1")
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    executed = await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert executed.status == ProposalStatus.EXECUTED
    cached = await email.get_message("user_1", provider_message_id="msg-1")
    assert "INBOX" not in cached.label_ids


async def test_approved_trash_executes_and_verifies() -> None:
    orchestrator, approvals, email, provider, _ = _orchestrator()
    await _connected(email)
    provider.trash_message_response = {"id": "msg-1", "labelIds": ["TRASH"]}
    provider.get_message_response = {"id": "msg-1", "labelIds": ["TRASH"]}

    proposal = await orchestrator.propose_trash("user_1", provider_message_id="msg-1")
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    executed = await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert executed.status == ProposalStatus.EXECUTED


async def test_draft_writes_are_not_cached_locally() -> None:
    """No dedicated list-drafts read capability exists (No Future
    Scaffolding) — the orchestrator must not attempt to cache a draft
    result as though it were a readable message."""
    orchestrator, approvals, email, _, messages_repo = _orchestrator()
    await _connected(email)

    proposal = await orchestrator.propose_create_draft(
        "user_1", to=["bob@example.com"], subject="Draft", body="wip"
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    executed = await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert executed.status == ProposalStatus.EXECUTED
    assert await messages_repo.get("user_1", "msg-1") is None
