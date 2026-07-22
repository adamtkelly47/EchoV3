from domains.email.write_adapters import (
    EmailArchiveVerifier,
    EmailArchiveWriteAdapter,
    EmailCreateDraftWriteAdapter,
    EmailDraftVerifier,
    EmailLabelVerifier,
    EmailLabelWriteAdapter,
    EmailSendVerifier,
    EmailSendWriteAdapter,
    EmailTrashVerifier,
    EmailTrashWriteAdapter,
)
from tests.unit.domains.email.fakes import FakeEmailProvider


async def test_create_draft_write_adapter_calls_provider_with_raw() -> None:
    provider = FakeEmailProvider()
    adapter = EmailCreateDraftWriteAdapter(provider, "token")

    result = await adapter.execute({"action": "create_draft", "raw_mime": "base64stuff"})

    assert result == provider.create_draft_response
    call = next(c for c in provider.calls if c[0] == "create_draft")
    assert call[1]["body"] == {"message": {"raw": "base64stuff"}}


async def test_draft_verifier_true_when_id_matches() -> None:
    provider = FakeEmailProvider()
    provider.get_draft_response = {"id": "draft-1"}
    verifier = EmailDraftVerifier(provider, "token")

    assert await verifier.verify({"id": "draft-1"}) is True


async def test_draft_verifier_false_when_no_id_in_result() -> None:
    provider = FakeEmailProvider()
    verifier = EmailDraftVerifier(provider, "token")

    assert await verifier.verify({}) is False


async def test_send_write_adapter_passes_raw_only() -> None:
    provider = FakeEmailProvider()
    adapter = EmailSendWriteAdapter(provider, "token")

    await adapter.execute({"action": "send_message", "raw_mime": "raw123"})

    call = next(c for c in provider.calls if c[0] == "send_message")
    assert call[1]["raw"] == "raw123"
    assert call[1]["thread_id"] is None


async def test_send_verifier_true_when_sent_label_present() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "sent-1", "labelIds": ["SENT"]}
    verifier = EmailSendVerifier(provider, "token")

    assert await verifier.verify({"id": "sent-1"}) is True


async def test_send_verifier_false_when_sent_label_missing() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "sent-1", "labelIds": ["INBOX"]}
    verifier = EmailSendVerifier(provider, "token")

    assert await verifier.verify({"id": "sent-1"}) is False


async def test_archive_write_adapter_removes_inbox_label() -> None:
    provider = FakeEmailProvider()
    adapter = EmailArchiveWriteAdapter(provider, "token")

    await adapter.execute({"action": "archive_message", "provider_message_id": "msg-1"})

    call = next(c for c in provider.calls if c[0] == "modify_labels")
    assert call[1]["remove_label_ids"] == ["INBOX"]
    assert call[1]["add_label_ids"] == []


async def test_archive_verifier_true_when_inbox_absent() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "msg-1", "labelIds": ["UNREAD"]}
    verifier = EmailArchiveVerifier(provider, "token")

    assert await verifier.verify({"id": "msg-1"}) is True


async def test_label_write_adapter_forwards_add_and_remove() -> None:
    provider = FakeEmailProvider()
    adapter = EmailLabelWriteAdapter(provider, "token")

    await adapter.execute(
        {
            "action": "label_message",
            "provider_message_id": "msg-1",
            "add_label_ids": ["STARRED"],
            "remove_label_ids": ["UNREAD"],
        }
    )

    call = next(c for c in provider.calls if c[0] == "modify_labels")
    assert call[1]["add_label_ids"] == ["STARRED"]
    assert call[1]["remove_label_ids"] == ["UNREAD"]


async def test_label_verifier_checks_both_add_and_remove() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "msg-1", "labelIds": ["STARRED", "INBOX"]}
    verifier = EmailLabelVerifier(provider, "token", ["STARRED"], ["UNREAD"])

    assert await verifier.verify({"id": "msg-1"}) is True


async def test_label_verifier_false_when_add_label_missing() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "msg-1", "labelIds": ["INBOX"]}
    verifier = EmailLabelVerifier(provider, "token", ["STARRED"], [])

    assert await verifier.verify({"id": "msg-1"}) is False


async def test_trash_write_adapter_calls_trash_endpoint() -> None:
    provider = FakeEmailProvider()
    adapter = EmailTrashWriteAdapter(provider, "token")

    result = await adapter.execute({"action": "trash_message", "provider_message_id": "msg-1"})

    assert result == provider.trash_message_response
    assert any(c[0] == "trash_message" for c in provider.calls)


async def test_trash_verifier_true_when_trash_label_present() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "msg-1", "labelIds": ["TRASH"]}
    verifier = EmailTrashVerifier(provider, "token")

    assert await verifier.verify({"id": "msg-1"}) is True


async def test_trash_verifier_false_when_trash_label_absent() -> None:
    provider = FakeEmailProvider()
    provider.get_message_response = {"id": "msg-1", "labelIds": ["INBOX"]}
    verifier = EmailTrashVerifier(provider, "token")

    assert await verifier.verify({"id": "msg-1"}) is False
