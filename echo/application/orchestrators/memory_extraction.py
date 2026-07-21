"""Memory candidate extraction using Ollama (PROMPT.md Phase 9 implement
item 2). Lives in application/orchestrators/ rather than inside
domains/memory/ because turning free-text into structured candidate facts
requires the Model Gateway — a cross-cutting concern the Application layer
coordinates, never a domain itself (CONSTITUTION.md: "the only layer
permitted to coordinate more than one domain simultaneously").

Extraction never confirms a memory itself (PROMPT.md Phase 9 verification:
"extracted candidates are not automatically treated as confirmed facts") —
every candidate this orchestrator records lands in MemoryStatus.CANDIDATE,
same as domains.memory.service.MemoryService.record_candidate's own contract.

Two model calls, not one — live-tested against llama3.2:1b (Docs/
DECISION_LOG.md's Phase 9 entry). A single combined "decide AND extract"
prompt produced hallucinated facts for non-fact messages and occasionally
echoed a few-shot example verbatim instead of processing the real message.
Splitting into a binary gate (has this message stated a durable fact at
all?) and a separate extraction call only when the gate says yes reused the
Capability Planner's proven pattern (Phase 8: a small model does zero-shot
classification unreliably but binary few-shot classification reliably) and
measured far more accurately in live testing. Two known limitations, found
live and not silently papered over:

1. A message stating two separate facts ("my name is Adam and I'm a
   software engineer") is extracted as a single bundled candidate —
   multi-fact splitting is not reliable at this model size and is not
   attempted here.
2. The gate generalizes narrowly: it reliably classifies messages at or
   near its few-shot examples, but a message worded differently from any
   example can still be misclassified — e.g. adding "What is the current
   date and time?" as a 7th example to cover that exact phrasing measurably
   *reduced* accuracy on the other six, rather than improving overall
   coverage (tested live). This looks like near-verbatim example matching
   rather than the general rule generalizing, which is a property of the
   1B model, not something more prompt engineering reliably fixes. The
   six-example set below is the empirically best-performing configuration
   found by live testing, not a claim of universal phrasing coverage.
"""

from __future__ import annotations

from pydantic import BaseModel

from application.model_gateway_factory import ModelGatewayPort
from core.errors import EchoError
from domains.memory.schemas import MemoryRecord
from domains.memory.service import MemoryService
from providers.models.contracts import ModelRequest, TaskType


class _DurableFactGateDecision(BaseModel):
    has_durable_fact: bool


class ExtractedMemoryCandidate(BaseModel):
    subject_key: str
    content: str
    confidence: float


_GATE_PROMPT = (
    "You are a classifier. Decide if this message states a durable, "
    "personal fact about the user that would still be true days or weeks "
    "from now (like a preference, an allergy, where they live, their job, "
    "their name). Questions, jokes, requests, and temporary states (like "
    "being tired or sick right now) are NOT durable facts.\n\n"
    "Examples:\n"
    'Message: "My favorite color is blue." -> {{"has_durable_fact": true}}\n'
    'Message: "I live in Seattle." -> {{"has_durable_fact": true}}\n'
    'Message: "What time is it?" -> {{"has_durable_fact": false}}\n'
    'Message: "I am pretty tired right now." -> {{"has_durable_fact": false}}\n'
    'Message: "Tell me a joke about cats." -> {{"has_durable_fact": false}}\n'
    'Message: "Can you write me a haiku?" -> {{"has_durable_fact": false}}\n\n'
    "Now classify this message. Reply with ONLY the JSON, nothing else.\n"
    'Message: "{message}"'
)

_EXTRACT_PROMPT = (
    "Extract the durable personal fact from this message as JSON. "
    'Rules: subject_key ALWAYS starts with "user." (e.g. user.favorite_color, '
    "user.location, user.allergy, user.occupation, user.name). content is "
    'ALWAYS rewritten in third person starting with "The user" (never "I"). '
    "confidence is 0.0 to 1.0.\n\n"
    "Examples:\n"
    'Message: "My favorite color is blue." -> {{"subject_key": '
    '"user.favorite_color", "content": "The user\'s favorite color is blue.", '
    '"confidence": 0.9}}\n'
    'Message: "I live in Seattle." -> {{"subject_key": "user.location", '
    '"content": "The user lives in Seattle.", "confidence": 0.9}}\n'
    'Message: "I am allergic to peanuts." -> {{"subject_key": "user.allergy", '
    '"content": "The user is allergic to peanuts.", "confidence": 0.9}}\n\n'
    "Now extract from this message. Reply with ONLY the JSON, nothing else.\n"
    'Message: "{message}"'
)


class MemoryExtractionOrchestrator:
    def __init__(self, memory: MemoryService, gateway: ModelGatewayPort) -> None:
        self._memory = memory
        self._gateway = gateway

    async def extract_and_record(
        self,
        text: str,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
        correlation_id: str | None = None,
    ) -> list[MemoryRecord]:
        candidate = await self._extract(text)
        if candidate is None:
            return []
        recorded = await self._memory.record_candidate(
            user_id=user_id,
            subject_key=candidate.subject_key,
            content=candidate.content,
            confidence=candidate.confidence,
            source_type=source_type,
            source_id=source_id,
            correlation_id=correlation_id,
        )
        return [recorded]

    async def _extract(self, text: str) -> ExtractedMemoryCandidate | None:
        if not await self._has_durable_fact(text):
            return None
        request = ModelRequest(
            task_type=TaskType.EXTRACTION,
            prompt=_EXTRACT_PROMPT.format(message=text),
            temperature=0.0,
        )
        try:
            return await self._gateway.generate_structured(request, ExtractedMemoryCandidate)
        except EchoError:
            return None  # fail safe: no candidate recorded rather than guessing

    async def _has_durable_fact(self, text: str) -> bool:
        request = ModelRequest(
            task_type=TaskType.CLASSIFICATION,
            prompt=_GATE_PROMPT.format(message=text),
            temperature=0.0,
        )
        try:
            decision = await self._gateway.generate_structured(request, _DurableFactGateDecision)
        except EchoError:
            return False  # fail safe: no capability invoked rather than guessing
        return decision.has_durable_fact
