"""Conversation owns active user interactions — "what is happening now"
(Docs/DOMAIN_OWNERSHIP.md). Minimal for Phase 8: a session and its
messages. Conversation summaries, artifacts, and active-intent tracking
are real DOMAIN_OWNERSHIP.md responsibilities but are not built until a
phase actually needs them (No Future Scaffolding).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.identifiers import new_id


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Channel(str, Enum):
    """PROMPT.md Phase 26 implement item 1: "input channel abstraction."
    A message's channel is just another fact about how it arrived — the
    same `handle_message`/`handle_message_stream` pipeline
    (application/orchestrators/conversation.py) handles both identically,
    per CONSTITUTION.md's Interface Independence ("No interface may
    implement unique business logic")."""

    TEXT = "text"
    VOICE = "voice"


class ConversationSession(BaseModel):
    session_id: str = Field(default_factory=lambda: new_id("conv"))
    user_id: str
    started_at: datetime
    status: str = "active"


class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: new_id("msg"))
    session_id: str
    role: MessageRole
    content: str
    created_at: datetime
    # Evidence backing an assistant response — e.g. the capability result a
    # reply was grounded in (Docs/CONSTITUTION.md: Evidence Collector/
    # Provenance). None for user messages.
    evidence: dict[str, Any] | None = None
    channel: Channel = Channel.TEXT
    # PROMPT.md Phase 26 implement item 4: "interruption handling contract."
    # True when a streamed assistant response was cut short by a real
    # interruption signal (domains/conversation/interfaces.py's
    # `InterruptSignal`) rather than completing naturally. Always False for
    # user messages.
    interrupted: bool = False
