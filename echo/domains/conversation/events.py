"""PROMPT.md Phase 26 implement items 2-3: "streaming transcript events"
and "response chunk events." Both ride `core/events/envelope.py`'s
`EventEnvelope[PayloadT]` — a generic, versioned, immutable wrapper that
has existed since an early phase but had no real publisher until now
(Docs/DECISION_LOG.md's Phase 26 entry). Reusing it here means a future
voice channel's transcript/response events are shaped identically to any
other domain event this codebase ever publishes, not a bespoke streaming
format invented just for voice.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.events.envelope import EventEnvelope


class TranscriptChunkPayload(BaseModel):
    """A partial (or final) speech-to-text result for one in-progress
    voice turn. `text` is the full transcript-so-far, not a delta — the
    same convention real streaming STT APIs use, so
    `ConversationOrchestrator.handle_transcript_stream` can simply take
    the latest chunk's `text` once `is_final` arrives."""

    session_id: str
    text: str
    is_final: bool


class ResponseChunkPayload(BaseModel):
    """One piece of an in-progress assistant reply — the same shape
    whether the reply was triggered by text or voice input, per
    CONSTITUTION.md's Interface Independence. `interrupted` is only ever
    True on the final chunk of a stream that was cut short (PROMPT.md
    Phase 26 implement item 4)."""

    session_id: str
    text: str
    is_final: bool
    interrupted: bool = False


TranscriptChunkEvent = EventEnvelope[TranscriptChunkPayload]
ResponseChunkEvent = EventEnvelope[ResponseChunkPayload]
