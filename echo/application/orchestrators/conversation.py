"""Coordinates Conversation + Capabilities + the Model Gateway for a single
turn — this is the Application layer's job (CONSTITUTION.md: "the only
layer permitted to coordinate more than one domain simultaneously"), a
minimal version of Docs/REQUEST_LIFECYCLE.md's pipeline: Intent Builder
(here: the raw message) -> Capability Planner -> Capability Executor ->
Evidence Collector -> Response Generator -> Persistence.

The Capability Planner asks the model gateway a structured yes/no question
("does answering this need the current time?") rather than string-matching
keywords in the message — CONSTITUTION.md: "Language models MAY propose
execution plans using registered capabilities," and capability *selection*
must not be reduced to prompt-wording pattern matching. If the model call
itself fails (e.g. schema validation), the planner fails safe to "no
capability needed" rather than guessing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import BaseModel

from application.capabilities.current_time import CAPABILITY_ID
from application.model_gateway_factory import ModelGatewayPort
from core.errors import EchoError
from core.events.envelope import EventEnvelope
from core.observability import get_correlation_id
from core.time import Clock
from domains.capabilities.service import CapabilityExecutor
from domains.conversation.events import (
    ResponseChunkEvent,
    ResponseChunkPayload,
    TranscriptChunkPayload,
)
from domains.conversation.interfaces import InterruptSignal
from domains.conversation.schemas import Channel, Message, MessageRole
from domains.conversation.service import ConversationService
from providers.models.contracts import ModelRequest, TaskType


class _TimeNeedDecision(BaseModel):
    needs_current_time: bool


_PLANNER_PROMPT = (
    "You are a classifier. Decide if answering the user's message requires "
    "knowing the current real-world date or time.\n\n"
    "Examples:\n"
    'Message: "What time is it?" -> {{"needs_current_time": true}}\n'
    'Message: "What day is today?" -> {{"needs_current_time": true}}\n'
    'Message: "Tell me a joke about cats" -> {{"needs_current_time": false}}\n'
    'Message: "What is 2+2?" -> {{"needs_current_time": false}}\n'
    'Message: "Write a haiku about the ocean" -> {{"needs_current_time": false}}\n\n'
    "Now classify this message. Reply with ONLY the JSON, nothing else.\n"
    'Message: "{message}"'
)

_RESPONSE_PROMPT_WITH_TIME = (
    "[SYSTEM FACT] The current date and time is {iso_timestamp}.\n"
    "You are an assistant with live access to this fact. Do not say you lack "
    "real-time access — you have just been given the real-time value above. "
    "Answer the user directly using it.\n\nUser: {message}\nAssistant:"
)

# Sampling temperature for calls where the model must state injected evidence
# rather than write freely — low, not zero, since Ollama's local models can
# still degenerate at temperature=0 (Docs/DECISION_LOG.md Phase 8). Framing
# the evidence as a "[SYSTEM FACT]" the model already possesses, rather than
# a live-lookup result it's being asked to relay, was what actually stopped
# the model's trained "I don't have real-time access" refusal reflex — a
# wording fix, not a sampling fix (Docs/DECISION_LOG.md Phase 8: the
# refusal was the model's highest-probability completion for the old
# wording even at temperature=0, so raising randomness would only have
# masked the problem, not fixed it).
_RESPONSE_TEMPERATURE = 0.1


class ConversationOrchestrator:
    def __init__(
        self,
        conversations: ConversationService,
        executor: CapabilityExecutor,
        gateway: ModelGatewayPort,
        clock: Clock,
    ) -> None:
        self._conversations = conversations
        self._executor = executor
        self._gateway = gateway
        self._clock = clock

    async def handle_message(
        self, session_id: str, text: str, *, channel: Channel = Channel.TEXT
    ) -> Message:
        await self._conversations.append_message(
            session_id, role=MessageRole.USER, content=text, channel=channel
        )

        evidence = await self._gather_evidence(text)
        prompt = self._build_response_prompt(text, evidence)
        response = await self._gateway.generate(
            ModelRequest(
                task_type=TaskType.CONVERSATION,
                prompt=prompt,
                temperature=_RESPONSE_TEMPERATURE if evidence else None,
            )
        )

        return await self._conversations.append_message(
            session_id,
            role=MessageRole.ASSISTANT,
            content=response.output,
            evidence=evidence,
            channel=channel,
        )

    async def handle_message_stream(
        self,
        session_id: str,
        text: str,
        *,
        channel: Channel = Channel.TEXT,
        interrupt: InterruptSignal | None = None,
    ) -> AsyncIterator[ResponseChunkEvent]:
        """Same pipeline as handle_message, but the Response Generator step
        streams — evidence gathering happens first and is not itself
        streamed (PROMPT.md Phase 8: "Streaming response API"). The full
        accumulated text is persisted as the assistant message once
        streaming completes. Every yielded chunk is a real
        `ResponseChunkEvent` (PROMPT.md Phase 26 implement item 3) — the
        one shape any channel (chat's `POST /messages/stream`, or a future
        voice channel) consumes, never raw, unwrapped text. `interrupt`
        (PROMPT.md Phase 26 implement item 4) is checked between chunks;
        when it fires, streaming stops early and the partial message is
        persisted with `interrupted=True` rather than silently discarded."""
        await self._conversations.append_message(
            session_id, role=MessageRole.USER, content=text, channel=channel
        )

        evidence = await self._gather_evidence(text)
        prompt = self._build_response_prompt(text, evidence)

        chunks: list[str] = []
        was_interrupted = False
        async for chunk in self._gateway.generate_stream(
            ModelRequest(
                task_type=TaskType.CONVERSATION,
                prompt=prompt,
                temperature=_RESPONSE_TEMPERATURE if evidence else None,
            )
        ):
            if interrupt is not None and await interrupt.is_interrupted():
                was_interrupted = True
                break
            chunks.append(chunk)
            yield EventEnvelope(
                event_type="conversation.response_chunk",
                occurred_at=self._clock.now_utc(),
                payload=ResponseChunkPayload(session_id=session_id, text=chunk, is_final=False),
            )

        yield EventEnvelope(
            event_type="conversation.response_chunk",
            occurred_at=self._clock.now_utc(),
            payload=ResponseChunkPayload(
                session_id=session_id, text="", is_final=True, interrupted=was_interrupted
            ),
        )

        await self._conversations.append_message(
            session_id,
            role=MessageRole.ASSISTANT,
            content="".join(chunks),
            evidence=evidence,
            channel=channel,
            interrupted=was_interrupted,
        )

    async def handle_transcript_stream(
        self,
        session_id: str,
        transcript_chunks: AsyncIterator[TranscriptChunkPayload],
        *,
        interrupt: InterruptSignal | None = None,
    ) -> AsyncIterator[ResponseChunkEvent]:
        """PROMPT.md Phase 26 implement item 2: "streaming transcript
        events." The concrete proof that voice input does not diverge
        from chat (this phase's own objective): once the transcript
        stream reports `is_final=True`, the accumulated text is handed to
        `handle_message_stream` unchanged — the exact same code path text
        input already uses, with `channel=Channel.VOICE` the only
        difference."""
        final_text = ""
        async for transcript in transcript_chunks:
            final_text = transcript.text
            if transcript.is_final:
                break

        async for event in self.handle_message_stream(
            session_id, final_text, channel=Channel.VOICE, interrupt=interrupt
        ):
            yield event

    async def _gather_evidence(self, text: str) -> dict[str, object] | None:
        if not await self._needs_current_time(text):
            return None
        result = await self._executor.execute(
            CAPABILITY_ID, {}, correlation_id=get_correlation_id()
        )
        return {"current_time": result.model_dump()}

    async def _needs_current_time(self, text: str) -> bool:
        request = ModelRequest(
            task_type=TaskType.CLASSIFICATION,
            prompt=_PLANNER_PROMPT.format(message=text),
            temperature=0.0,
        )
        try:
            decision = await self._gateway.generate_structured(request, _TimeNeedDecision)
        except EchoError:
            return False  # fail safe: no capability invoked rather than guessing
        return decision.needs_current_time

    def _build_response_prompt(self, text: str, evidence: dict[str, object] | None) -> str:
        if evidence and "current_time" in evidence:
            iso_timestamp = evidence["current_time"]["iso_timestamp"]  # type: ignore[index]
            return _RESPONSE_PROMPT_WITH_TIME.format(iso_timestamp=iso_timestamp, message=text)
        return text
