"""Email's own data contracts (Docs/DOMAIN_OWNERSHIP.md: Email owns Email
Messages, Threads, Attachments, Email Classification). Derived from Gmail
API v1's real Message resource (developers.google.com/gmail/api/reference/rest/v1/users.messages)
but kept provider-agnostic in field naming, matching domains/calendar/schemas.py.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.email.models import EmailCategory


class EmailCredential(BaseModel):
    """OAuth token state for one user's connection to one provider. Tokens
    are stored encrypted (Docs/SECURITY.md) — this schema holds ciphertext,
    never plaintext tokens; domains/email/service.py is the only place that
    ever sees a decrypted token, and only for the duration of a single
    provider call."""

    credential_id: str = Field(default_factory=lambda: new_id("emailcred"))
    user_id: str
    provider: str = "gmail"
    encrypted_access_token: str
    encrypted_refresh_token: str
    access_token_expires_at: datetime
    scope: str
    created_at: datetime
    updated_at: datetime


class EmailAttachmentMeta(BaseModel):
    """Metadata only — no attachment bytes are ever fetched or stored
    (PROMPT.md Phase 20 implement item 7: "safe attachment handling")."""

    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int


class MessageClassification(BaseModel):
    """Local-model output (PROMPT.md Phase 20 implement items 9-11: local
    classification, action item extraction, response needed detection) —
    treated as candidate analysis, never verified truth (PROMPT.md section
    12.1)."""

    category: EmailCategory
    needs_response: bool
    action_items: list[str] = Field(default_factory=list)
    classified_at: datetime


class EmailMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: new_id("emailmsg"))
    user_id: str
    provider_message_id: str
    thread_id: str
    subject: str
    snippet: str
    from_address: str
    to_addresses: list[str] = Field(default_factory=list)
    date: datetime
    label_ids: list[str] = Field(default_factory=list)
    is_unread: bool = True
    attachments: list[EmailAttachmentMeta] = Field(default_factory=list)
    classification: MessageClassification | None = None
    # The RFC 2822 `Message-ID` header (distinct from Gmail's own `id`
    # field) — needed to build a correctly-threaded reply's `In-Reply-To`/
    # `References` headers (application/orchestrators/email_writes.py).
    rfc_message_id: str | None = None
    # When this message was last fetched from the provider (PROMPT.md Phase
    # 20 implement item 8: email cache) — set by domains/email/service.py
    # using its injected Clock, never by a provider adapter.
    synced_at: datetime
