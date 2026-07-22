"""Email intelligence: local classification, action-item extraction, and
response-needed detection (PROMPT.md Phase 20 implement items 9-11) all run
against Ollama in a single structured call per message — cheaper and
simpler than three separate calls for the same input (PROMPT.md section
3.6: Cost Discipline) — plus on-demand thread summarization (section 21's
"summarize threads" read capability). Lives in application/orchestrators/
rather than inside domains/email/ because it needs the Model Gateway (a
cross-cutting concern only the Application layer may reach for), matching
application/orchestrators/news_intelligence.py's and
application/orchestrators/memory_extraction.py's identical placement
rationale. Local-model output is treated as candidate analysis, never
verified truth (PROMPT.md section 12.1) — every fallback below fails safe
(no guess) rather than fabricating a confident answer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from application.model_gateway_factory import ModelGatewayPort
from core.errors import EchoError
from core.time import Clock
from domains.email.models import EmailCategory
from domains.email.schemas import EmailMessage, MessageClassification
from domains.email.service import EmailService
from providers.models.contracts import ModelRequest, TaskType


class _ClassificationOutput(BaseModel):
    category: EmailCategory
    needs_response: bool
    action_items: list[str] = Field(default_factory=list)


class _SummaryOutput(BaseModel):
    summary: str


_CLASSIFY_PROMPT = (
    "Classify this email using ONLY the information given below — do not "
    "assume facts not stated.\n\n"
    "Categories (choose exactly one):\n"
    '- "action_needed": the sender is asking the recipient to do something\n'
    '- "awaiting_response": the sender is asking a question expecting a reply\n'
    '- "informational": a notice, update, or FYI with nothing required\n'
    '- "promotional": marketing, newsletters, or automated offers\n'
    '- "other": anything that clearly does not fit the above\n\n'
    "Also decide whether this email needs a response from the recipient, "
    "and list any concrete action items stated in the email (empty list if "
    "none). Do not invent action items not actually present in the text.\n\n"
    'Subject: "{subject}"\n'
    'From: "{sender}"\n'
    'Body excerpt: "{snippet}"\n\n'
    "Reply with ONLY a JSON object of the exact form "
    '{{"category": "<category>", "needs_response": <true|false>, '
    '"action_items": ["<item>", ...]}}, nothing else.'
)

_SUMMARIZE_THREAD_PROMPT = (
    "Summarize this email thread in two or three sentences. Use ONLY the "
    "numbered messages given below — never add outside information or "
    "facts not present in the text.\n\n"
    "{numbered_messages}\n\n"
    "Reply with ONLY a JSON object of the exact form "
    '{{"summary": "<your two or three sentence summary>"}}, nothing else.'
)


class EmailIntelligenceOrchestrator:
    def __init__(self, email: EmailService, gateway: ModelGatewayPort, clock: Clock) -> None:
        self._email = email
        self._gateway = gateway
        self._clock = clock

    async def classify_message(
        self, user_id: str, *, provider_message_id: str
    ) -> MessageClassification:
        message = await self._email.get_message(user_id, provider_message_id=provider_message_id)
        classification = await self._classify(message)
        await self._email.save_classification(user_id, provider_message_id, classification)
        return classification

    async def _classify(self, message: EmailMessage) -> MessageClassification:
        request = ModelRequest(
            task_type=TaskType.CLASSIFICATION,
            prompt=_CLASSIFY_PROMPT.format(
                subject=message.subject, sender=message.from_address, snippet=message.snippet
            ),
            temperature=0.0,
        )
        now = self._clock.now_utc()
        try:
            result = await self._gateway.generate_structured(request, _ClassificationOutput)
        except EchoError:
            # Fail safe: no confident guess about category/response-needed/
            # action items when the model call itself failed or produced
            # invalid output — matching news_intelligence's identical
            # fallback philosophy.
            return MessageClassification(
                category=EmailCategory.OTHER,
                needs_response=False,
                action_items=[],
                classified_at=now,
            )
        return MessageClassification(
            category=result.category,
            needs_response=result.needs_response,
            action_items=result.action_items,
            classified_at=now,
        )

    async def summarize_thread(self, user_id: str, *, thread_id: str) -> str:
        messages = await self._email.get_thread(user_id, thread_id=thread_id)
        if not messages:
            return "No messages found in this thread."

        numbered = "\n".join(
            f"[{i + 1}] From {m.from_address} ({m.date.date().isoformat()}): {m.snippet}"
            for i, m in enumerate(messages)
        )
        request = ModelRequest(
            task_type=TaskType.SUMMARIZATION,
            prompt=_SUMMARIZE_THREAD_PROMPT.format(numbered_messages=numbered),
            temperature=0.0,
        )
        try:
            result = await self._gateway.generate_structured(request, _SummaryOutput)
        except EchoError:
            return f"Summary unavailable — {len(messages)} message(s) in thread."
        return result.summary
