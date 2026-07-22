from datetime import UTC, datetime, timedelta

import pytest

from domains.email.errors import EmailOAuthStateInvalidError
from domains.email.models import EmailCategory
from domains.email.policies import (
    classification_from_model_output,
    generate_oauth_state,
    is_stale,
    needs_refresh,
    parse_attachments,
    parse_email_addresses,
    parse_message,
    verify_oauth_state,
)
from domains.email.schemas import EmailCredential


def _credential(expires_at: datetime) -> EmailCredential:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return EmailCredential(
        user_id="user_1",
        encrypted_access_token="enc-access",
        encrypted_refresh_token="enc-refresh",
        access_token_expires_at=expires_at,
        scope="https://www.googleapis.com/auth/gmail.readonly",
        created_at=now,
        updated_at=now,
    )


def test_needs_refresh_true_inside_buffer() -> None:
    credential = _credential(datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC))
    assert needs_refresh(credential, datetime(2026, 1, 1, 12, 58, 0, tzinfo=UTC)) is True


def test_needs_refresh_false_outside_buffer() -> None:
    credential = _credential(datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC))
    assert needs_refresh(credential, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)) is False


def test_is_stale() -> None:
    synced_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert is_stale(synced_at, synced_at + timedelta(minutes=10), timedelta(minutes=5)) is True
    assert is_stale(synced_at, synced_at + timedelta(minutes=2), timedelta(minutes=5)) is False


def test_parse_email_addresses_extracts_bracketed_address() -> None:
    assert parse_email_addresses('"Jane Doe" <jane@example.com>, bob@example.com') == [
        "jane@example.com",
        "bob@example.com",
    ]


def test_parse_email_addresses_handles_none() -> None:
    assert parse_email_addresses(None) == []


def test_parse_attachments_extracts_metadata_only() -> None:
    payload = {
        "parts": [
            {"filename": "", "mimeType": "text/plain", "body": {"size": 100}},
            {
                "filename": "report.pdf",
                "mimeType": "application/pdf",
                "body": {"attachmentId": "att-1", "size": 2048},
            },
        ]
    }
    attachments = parse_attachments(payload)
    assert len(attachments) == 1
    assert attachments[0].attachment_id == "att-1"
    assert attachments[0].filename == "report.pdf"
    assert attachments[0].size_bytes == 2048


def test_parse_message_extracts_headers_and_message_id() -> None:
    raw = {
        "id": "msg-1",
        "threadId": "thread-1",
        "snippet": "hello there",
        "labelIds": ["INBOX", "UNREAD"],
        "internalDate": "1767268800000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "To", "value": "Bob <bob@example.com>"},
                {"name": "Message-ID", "value": "<abc123@mail.gmail.com>"},
            ],
            "parts": [],
        },
    }
    message = parse_message(raw, user_id="user_1", synced_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert message.subject == "Hello"
    assert message.from_address == "alice@example.com"
    assert message.to_addresses == ["bob@example.com"]
    assert message.is_unread is True
    assert message.rfc_message_id == "<abc123@mail.gmail.com>"


def test_classification_from_model_output_assembles_dict() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = classification_from_model_output(
        category=EmailCategory.ACTION_NEEDED, needs_response=True, action_items=["reply"], now=now
    )
    assert result == {
        "category": EmailCategory.ACTION_NEEDED,
        "needs_response": True,
        "action_items": ["reply"],
        "classified_at": now,
    }


def test_oauth_state_round_trips_user_id() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-1", now, "secret")
    assert verify_oauth_state(state, "secret", now) == "user_1"


def test_oauth_state_rejects_wrong_secret() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-1", now, "secret")
    with pytest.raises(EmailOAuthStateInvalidError):
        verify_oauth_state(state, "different-secret", now)


def test_oauth_state_rejects_expired() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-1", now, "secret")
    with pytest.raises(EmailOAuthStateInvalidError):
        verify_oauth_state(state, "secret", now + timedelta(minutes=11))


def test_oauth_state_rejects_malformed() -> None:
    with pytest.raises(EmailOAuthStateInvalidError):
        verify_oauth_state("not-valid-base64-!!!", "secret", datetime(2026, 1, 1, tzinfo=UTC))
