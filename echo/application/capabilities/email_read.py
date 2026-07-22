"""Email read capabilities (PROMPT.md Phase 20 implement item — matching
domains/calendar's Phase 10 "calendar capability definitions" precedent;
Docs/CAPABILITY_REGISTRY.md: "search email" is named as an illustrative
category — this is that capability, now real). Lives under
application/capabilities/ per CONSTITUTION.md's Application Structure, same
placement as application/capabilities/calendar_read.py.

The capability registry is built once at process start
(apps/api/dependencies.py's `get_capability_registry` is `@lru_cache`d),
before any per-request session exists — so the handler opens its own
`session_scope()` per call, matching calendar_read.py's identical reasoning.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.capabilities import CapabilityContract, ExecutionEnvironment, ReadWriteClassification
from core.security import Permission, PermissionAction
from core.time import SystemClock
from domains.capabilities.models import RegisteredCapability
from domains.email.repository import (
    PostgresEmailCredentialRepository,
    PostgresEmailMessageRepository,
)
from domains.email.service import EmailProviderPort, EmailService
from infrastructure.database.engine import session_scope
from infrastructure.database.repositories.audit import PostgresAuditRepository
from infrastructure.secrets.encryption import SecretCipher

SEARCH_MESSAGES_CAPABILITY_ID = "email.search_messages"

_READ_PERMISSION = [Permission(resource="email", action=PermissionAction.READ)]


class SearchMessagesInput(BaseModel):
    user_id: str
    query: str | None = None
    max_results: int = 10


class EmailMessageSummary(BaseModel):
    provider_message_id: str
    thread_id: str
    subject: str
    snippet: str
    from_address: str
    date: datetime
    is_unread: bool


class SearchMessagesOutput(BaseModel):
    messages: list[EmailMessageSummary]


def _build_email_service(
    session: AsyncSession, provider: EmailProviderPort, cipher: SecretCipher, state_secret: str
) -> EmailService:
    return EmailService(
        PostgresEmailCredentialRepository(session),
        PostgresEmailMessageRepository(session),
        provider,
        cipher,
        PostgresAuditRepository(session),
        SystemClock(),
        state_secret,
    )


def build_email_search_messages_capability(
    provider: EmailProviderPort, cipher: SecretCipher, state_secret: str
) -> RegisteredCapability:
    async def handler(raw_data: BaseModel) -> BaseModel:
        # CapabilityExecutor._validate_input already guarantees raw_data is
        # exactly this handler's input_model — a type-narrowing cast, not a
        # runtime invariant check.
        data = cast(SearchMessagesInput, raw_data)
        async with session_scope() as session:
            email = _build_email_service(session, provider, cipher, state_secret)
            messages = await email.search_messages(
                data.user_id, query=data.query, max_results=data.max_results
            )
        return SearchMessagesOutput(
            messages=[
                EmailMessageSummary(
                    provider_message_id=m.provider_message_id,
                    thread_id=m.thread_id,
                    subject=m.subject,
                    snippet=m.snippet,
                    from_address=m.from_address,
                    date=m.date,
                    is_unread=m.is_unread,
                )
                for m in messages
            ]
        )

    contract = CapabilityContract(
        capability_id=SEARCH_MESSAGES_CAPABILITY_ID,
        version=1,
        display_name="Search email messages",
        description="Searches (or lists recent) messages in the user's Gmail inbox.",
        owner="Email",
        input_schema=SearchMessagesInput.model_json_schema(),
        output_schema=SearchMessagesOutput.model_json_schema(),
        permission_requirements=_READ_PERMISSION,
        execution_environment=ExecutionEnvironment.REQUEST,
        read_write_classification=ReadWriteClassification.READ,
        timeout_seconds=30,
        idempotency_behavior="read only — safe to call repeatedly",
        provenance_requirements="source=gmail; synced_at recorded per message",
        supported_interfaces=["chat", "api"],
        expected_errors=["email_credential_not_found", "email_token_refresh_failed"],
    )
    return RegisteredCapability(
        contract=contract,
        input_model=SearchMessagesInput,
        output_model=SearchMessagesOutput,
        handler=handler,
    )
