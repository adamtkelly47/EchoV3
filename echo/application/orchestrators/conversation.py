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
from core.observability import get_correlation_id
from domains.capabilities.service import CapabilityExecutor
from domains.conversation.schemas import Message, MessageRole
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
    ) -> None:
        self._conversations = conversations
        self._executor = executor
        self._gateway = gateway

    async def handle_message(self, session_id: str, text: str) -> Message:
        await self._conversations.append_message(session_id, role=MessageRole.USER, content=text)

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
            session_id, role=MessageRole.ASSISTANT, content=response.output, evidence=evidence
        )

    async def handle_message_stream(self, session_id: str, text: str) -> AsyncIterator[str]:
        """Same pipeline as handle_message, but the Response Generator step
        streams — evidence gathering happens first and is not itself
        streamed (PROMPT.md Phase 8: "Streaming response API"). The full
        accumulated text is persisted as the assistant message once
        streaming completes."""
        await self._conversations.append_message(session_id, role=MessageRole.USER, content=text)

        evidence = await self._gather_evidence(text)
        prompt = self._build_response_prompt(text, evidence)

        chunks: list[str] = []
        async for chunk in self._gateway.generate_stream(
            ModelRequest(
                task_type=TaskType.CONVERSATION,
                prompt=prompt,
                temperature=_RESPONSE_TEMPERATURE if evidence else None,
            )
        ):
            chunks.append(chunk)
            yield chunk

        await self._conversations.append_message(
            session_id, role=MessageRole.ASSISTANT, content="".join(chunks), evidence=evidence
        )

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
