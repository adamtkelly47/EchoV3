"""API-boundary request/response schemas — never the domain's own
EmailMessage/EmailCredential crossing the wire directly (CONSTITUTION.md:
Typed Contracts), matching apps/api/schemas/calendar.py's convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConnectCallbackResponse(BaseModel):
    user_id: str
    connected: bool


class EmailAttachmentResponse(BaseModel):
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int


class MessageClassificationResponse(BaseModel):
    category: str
    needs_response: bool
    action_items: list[str]
    classified_at: datetime


class EmailMessageResponse(BaseModel):
    provider_message_id: str
    thread_id: str
    subject: str
    snippet: str
    from_address: str
    to_addresses: list[str]
    date: datetime
    label_ids: list[str]
    is_unread: bool
    attachments: list[EmailAttachmentResponse]
    classification: MessageClassificationResponse | None
    synced_at: datetime


class MessageListResponse(BaseModel):
    messages: list[EmailMessageResponse]


class ThreadSummaryResponse(BaseModel):
    thread_id: str
    summary: str


class CreateDraftRequest(BaseModel):
    user_id: str
    to: list[str]
    subject: str
    body: str
    cc: list[str] | None = None


class UpdateDraftRequest(BaseModel):
    user_id: str
    to: list[str]
    subject: str
    body: str
    cc: list[str] | None = None


class SendMessageRequest(BaseModel):
    user_id: str
    to: list[str]
    subject: str
    body: str
    cc: list[str] | None = None


class ReplyRequest(BaseModel):
    user_id: str
    body: str
    to: list[str] | None = None


class LabelRequest(BaseModel):
    user_id: str
    add_label_ids: list[str] | None = None
    remove_label_ids: list[str] | None = None
