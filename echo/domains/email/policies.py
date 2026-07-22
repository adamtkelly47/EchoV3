"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as domains/calendar/policies.py.
This is also where Gmail's raw JSON (returned as plain dicts by
domains.email.service.EmailProviderPort, matching the providers-must-not-
import-domains precedent) gets translated into Email's own typed schemas —
the one place that translation happens.

OAuth state signing is a near-verbatim duplicate of
domains/calendar/policies.py's generate_oauth_state/verify_oauth_state
rather than a shared import — domains do not import each other
(Docs/DOMAIN_OWNERSHIP.md dependency rules), and the function is small
enough that duplicating it here costs less than inventing a shared
cross-domain module for two call sites.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from domains.email.errors import EmailOAuthStateInvalidError
from domains.email.models import EmailCategory
from domains.email.schemas import EmailAttachmentMeta, EmailCredential, EmailMessage

_HEADER_SUBJECT = "Subject"
_HEADER_FROM = "From"
_HEADER_TO = "To"
_HEADER_MESSAGE_ID = "Message-ID"


def needs_refresh(
    credential: EmailCredential, now: datetime, buffer: timedelta = timedelta(minutes=5)
) -> bool:
    """Refresh a little before actual expiry, not exactly at it — avoids a
    request racing the expiry boundary and failing with a stale token."""
    return now >= (credential.access_token_expires_at - buffer)


def is_stale(synced_at: datetime, now: datetime, max_age: timedelta) -> bool:
    return now - synced_at > max_age


def _headers_dict(payload: dict[str, Any]) -> dict[str, str]:
    return {h["name"]: h["value"] for h in payload.get("headers", [])}


def _get_header(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive lookup — Gmail's own header casing (e.g.
    `Message-ID` vs. `Message-Id`) isn't guaranteed to match a fixed
    constant exactly."""
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def parse_email_addresses(header_value: str | None) -> list[str]:
    """Gmail's From/To headers are a comma-separated list of RFC 5322
    mailbox strings (often `"Display Name <addr@example.com>"`) — this
    extracts just the bracketed or bare address, never the display name,
    since only the address is needed for sending/replying."""
    if not header_value:
        return []
    addresses = []
    for part in header_value.split(","):
        part = part.strip()
        if "<" in part and ">" in part:
            part = part[part.index("<") + 1 : part.index(">")]
        if part:
            addresses.append(part.strip())
    return addresses


def parse_attachments(payload: dict[str, Any]) -> list[EmailAttachmentMeta]:
    """Only metadata (filename/mimeType/attachmentId/size) is ever
    extracted — no attachment body is fetched (PROMPT.md Phase 20 implement
    item 7: "safe attachment handling"), matching Gmail's documented
    MessagePart shape (developers.google.com/gmail/api/reference/rest/v1/
    users.messages#messagepart)."""
    attachments: list[EmailAttachmentMeta] = []
    for part in payload.get("parts", []) or []:
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            attachments.append(
                EmailAttachmentMeta(
                    attachment_id=attachment_id,
                    filename=filename,
                    mime_type=part.get("mimeType", "application/octet-stream"),
                    size_bytes=body.get("size", 0),
                )
            )
    return attachments


def parse_message(raw: dict[str, Any], *, user_id: str, synced_at: datetime) -> EmailMessage:
    """The one place a raw Gmail message dict (format=full, i.e. including
    `payload`) becomes a domain EmailMessage."""
    payload = raw.get("payload", {})
    headers = _headers_dict(payload)
    label_ids = raw.get("labelIds", [])
    # internalDate is Gmail's own ms-since-epoch receipt timestamp — used in
    # preference to the (attacker-controllable, sometimes missing/malformed)
    # Date header, matching Gmail's own documented recommendation.
    internal_date_ms = raw.get("internalDate")
    date = (
        datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=UTC)
        if internal_date_ms
        else synced_at
    )
    return EmailMessage(
        user_id=user_id,
        provider_message_id=raw["id"],
        thread_id=raw.get("threadId", raw["id"]),
        subject=_get_header(headers, _HEADER_SUBJECT) or "(no subject)",
        snippet=raw.get("snippet", ""),
        from_address=(parse_email_addresses(_get_header(headers, _HEADER_FROM)) or [""])[0],
        to_addresses=parse_email_addresses(_get_header(headers, _HEADER_TO)),
        date=date,
        label_ids=label_ids,
        is_unread="UNREAD" in label_ids,
        attachments=parse_attachments(payload),
        rfc_message_id=_get_header(headers, _HEADER_MESSAGE_ID),
        synced_at=synced_at,
    )


def classification_from_model_output(
    *, category: EmailCategory, needs_response: bool, action_items: list[str], now: datetime
) -> dict[str, Any]:
    """Assembles the classification dict domains/email/service.py stores
    onto a message — a thin, pure seam so
    application/orchestrators/email_intelligence.py never constructs the
    stored shape itself."""
    return {
        "category": category,
        "needs_response": needs_response,
        "action_items": action_items,
        "classified_at": now,
    }


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_oauth_state(user_id: str, nonce: str, now: datetime, secret: str) -> str:
    """Docs/SECURITY.md: "Redirect target validation on OAuth callback
    flows." A signed, timestamped token rather than a server-side session
    store — matching domains/calendar/policies.py's identical rationale."""
    payload = f"{user_id}:{nonce}:{now.timestamp()}"
    signature = _sign(payload, secret)
    token = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")


def verify_oauth_state(
    state: str, secret: str, now: datetime, max_age: timedelta = timedelta(minutes=10)
) -> str:
    """Returns the user_id embedded in a valid, fresh, correctly-signed
    state token — raises EmailOAuthStateInvalidError otherwise (bad
    signature, tampered payload, or expired)."""
    try:
        decoded = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
        user_id, nonce, timestamp_str, signature = decoded.rsplit(":", 3)
    except (ValueError, UnicodeDecodeError) as exc:
        raise EmailOAuthStateInvalidError("malformed OAuth state") from exc

    payload = f"{user_id}:{nonce}:{timestamp_str}"
    expected = _sign(payload, secret)
    if not hmac.compare_digest(signature, expected):
        raise EmailOAuthStateInvalidError("OAuth state signature mismatch")

    try:
        issued_at = datetime.fromtimestamp(float(timestamp_str), tz=UTC)
    except ValueError as exc:
        raise EmailOAuthStateInvalidError("malformed OAuth state timestamp") from exc
    if now - issued_at > max_age:
        raise EmailOAuthStateInvalidError("OAuth state expired")

    return user_id
