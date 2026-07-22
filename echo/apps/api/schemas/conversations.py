"""API-boundary request/response schemas — never the domain's own
ActionProposal/Message/etc. crossing the wire directly (CONSTITUTION.md:
Typed Contracts), so the API's wire shape can evolve independently of the
domain's internal representation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StartConversationResponse(BaseModel):
    session_id: str
    started_at: datetime


class SendMessageRequest(BaseModel):
    content: str
    channel: str = "text"


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: datetime
    evidence: dict[str, Any] | None = None
    channel: str
    interrupted: bool


class ConversationHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageResponse]


class ResponseChunkResponse(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    session_id: str
    text: str
    is_final: bool
    interrupted: bool
