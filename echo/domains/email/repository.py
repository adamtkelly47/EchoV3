"""Email owns its own persistence — credentials and cached messages are
domain-owned aggregates (Docs/DOMAIN_OWNERSHIP.md: "Email repositories own:
messages, threads, drafts, labels"), so the ORM tables live here rather than
under infrastructure/database/tables/ — matching the Calendar (Phase 10),
Approvals (Phase 6), Conversation (Phase 8), and Memory (Phase 9) precedent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Boolean, DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.email.models import EmailCategory
from domains.email.schemas import (
    EmailAttachmentMeta,
    EmailCredential,
    EmailMessage,
    MessageClassification,
)
from infrastructure.database.base import Base


class EmailCredentialRow(Base):
    __tablename__ = "email_credentials"

    credential_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    provider: Mapped[str] = mapped_column(String)
    encrypted_access_token: Mapped[str] = mapped_column(String)
    encrypted_refresh_token: Mapped[str] = mapped_column(String)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmailMessageRow(Base):
    __tablename__ = "email_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    provider_message_id: Mapped[str] = mapped_column(String, index=True)
    thread_id: Mapped[str] = mapped_column(String, index=True)
    subject: Mapped[str] = mapped_column(String)
    snippet: Mapped[str] = mapped_column(String)
    from_address: Mapped[str] = mapped_column(String)
    to_addresses: Mapped[list[str]] = mapped_column(JSONB, default=list)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    label_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_unread: Mapped[bool] = mapped_column(Boolean)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    rfc_message_id: Mapped[str | None] = mapped_column(String)
    classification_category: Mapped[str | None] = mapped_column(String)
    classification_needs_response: Mapped[bool | None] = mapped_column(Boolean)
    classification_action_items: Mapped[list[str] | None] = mapped_column(JSONB)
    classification_classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _attachments_to_json(attachments: list[EmailAttachmentMeta]) -> list[dict[str, Any]]:
    return [a.model_dump() for a in attachments]


def _attachments_from_json(raw: list[dict[str, Any]] | None) -> list[EmailAttachmentMeta]:
    return [EmailAttachmentMeta(**item) for item in (raw or [])]


def _classification_from_row(row: EmailMessageRow) -> MessageClassification | None:
    if row.classification_category is None or row.classification_classified_at is None:
        return None
    return MessageClassification(
        category=EmailCategory(row.classification_category),
        needs_response=bool(row.classification_needs_response),
        action_items=list(row.classification_action_items or []),
        classified_at=row.classification_classified_at,
    )


def _message_to_row(message: EmailMessage) -> EmailMessageRow:
    row = EmailMessageRow(
        message_id=message.message_id,
        user_id=message.user_id,
        provider_message_id=message.provider_message_id,
        thread_id=message.thread_id,
        subject=message.subject,
        snippet=message.snippet,
        from_address=message.from_address,
        to_addresses=message.to_addresses,
        date=message.date,
        label_ids=message.label_ids,
        is_unread=message.is_unread,
        attachments=_attachments_to_json(message.attachments),
        rfc_message_id=message.rfc_message_id,
        synced_at=message.synced_at,
    )
    _apply_classification(row, message.classification)
    return row


def _apply_classification(
    row: EmailMessageRow, classification: MessageClassification | None
) -> None:
    if classification is None:
        return
    row.classification_category = classification.category.value
    row.classification_needs_response = classification.needs_response
    row.classification_action_items = classification.action_items
    row.classification_classified_at = classification.classified_at


def _row_to_message(row: EmailMessageRow) -> EmailMessage:
    return EmailMessage(
        message_id=row.message_id,
        user_id=row.user_id,
        provider_message_id=row.provider_message_id,
        thread_id=row.thread_id,
        subject=row.subject,
        snippet=row.snippet,
        from_address=row.from_address,
        to_addresses=list(row.to_addresses or []),
        date=row.date,
        label_ids=list(row.label_ids or []),
        is_unread=row.is_unread,
        attachments=_attachments_from_json(row.attachments),
        rfc_message_id=row.rfc_message_id,
        classification=_classification_from_row(row),
        synced_at=row.synced_at,
    )


class EmailCredentialRepository(Protocol):
    async def save(self, credential: EmailCredential) -> None: ...
    async def get_for_user(self, user_id: str) -> EmailCredential | None: ...


class EmailMessageRepository(Protocol):
    async def upsert_many(self, messages: list[EmailMessage]) -> None: ...
    async def list_recent(self, user_id: str, *, limit: int = 25) -> list[EmailMessage]: ...
    async def list_by_thread(self, user_id: str, thread_id: str) -> list[EmailMessage]: ...
    async def get(self, user_id: str, provider_message_id: str) -> EmailMessage | None: ...
    async def save_classification(
        self, user_id: str, provider_message_id: str, classification: MessageClassification
    ) -> None: ...


class PostgresEmailCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, credential: EmailCredential) -> None:
        existing = await self._get_row(credential.user_id)
        if existing is None:
            self._session.add(
                EmailCredentialRow(
                    credential_id=credential.credential_id,
                    user_id=credential.user_id,
                    provider=credential.provider,
                    encrypted_access_token=credential.encrypted_access_token,
                    encrypted_refresh_token=credential.encrypted_refresh_token,
                    access_token_expires_at=credential.access_token_expires_at,
                    scope=credential.scope,
                    created_at=credential.created_at,
                    updated_at=credential.updated_at,
                )
            )
        else:
            existing.encrypted_access_token = credential.encrypted_access_token
            existing.encrypted_refresh_token = credential.encrypted_refresh_token
            existing.access_token_expires_at = credential.access_token_expires_at
            existing.scope = credential.scope
            existing.updated_at = credential.updated_at
        await self._session.flush()

    async def get_for_user(self, user_id: str) -> EmailCredential | None:
        row = await self._get_row(user_id)
        if row is None:
            return None
        return EmailCredential(
            credential_id=row.credential_id,
            user_id=row.user_id,
            provider=row.provider,
            encrypted_access_token=row.encrypted_access_token,
            encrypted_refresh_token=row.encrypted_refresh_token,
            access_token_expires_at=row.access_token_expires_at,
            scope=row.scope,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _get_row(self, user_id: str) -> EmailCredentialRow | None:
        result = await self._session.execute(
            select(EmailCredentialRow).where(EmailCredentialRow.user_id == user_id)
        )
        return result.scalar_one_or_none()


class PostgresEmailMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, messages: list[EmailMessage]) -> None:
        for message in messages:
            existing = await self._get_row(message.user_id, message.provider_message_id)
            if existing is None:
                self._session.add(_message_to_row(message))
            else:
                self._update_row(existing, message)
        await self._session.flush()

    def _update_row(self, row: EmailMessageRow, message: EmailMessage) -> None:
        row.subject = message.subject
        row.snippet = message.snippet
        row.from_address = message.from_address
        row.to_addresses = message.to_addresses
        row.date = message.date
        row.label_ids = message.label_ids
        row.is_unread = message.is_unread
        row.attachments = _attachments_to_json(message.attachments)
        row.rfc_message_id = message.rfc_message_id
        row.synced_at = message.synced_at
        _apply_classification(row, message.classification)

    async def list_recent(self, user_id: str, *, limit: int = 25) -> list[EmailMessage]:
        result = await self._session.execute(
            select(EmailMessageRow)
            .where(EmailMessageRow.user_id == user_id)
            .order_by(EmailMessageRow.date.desc())
            .limit(limit)
        )
        return [_row_to_message(row) for row in result.scalars().all()]

    async def list_by_thread(self, user_id: str, thread_id: str) -> list[EmailMessage]:
        result = await self._session.execute(
            select(EmailMessageRow)
            .where(EmailMessageRow.user_id == user_id, EmailMessageRow.thread_id == thread_id)
            .order_by(EmailMessageRow.date.asc())
        )
        return [_row_to_message(row) for row in result.scalars().all()]

    async def get(self, user_id: str, provider_message_id: str) -> EmailMessage | None:
        row = await self._get_row(user_id, provider_message_id)
        return _row_to_message(row) if row is not None else None

    async def save_classification(
        self, user_id: str, provider_message_id: str, classification: MessageClassification
    ) -> None:
        row = await self._get_row(user_id, provider_message_id)
        if row is not None:
            _apply_classification(row, classification)
            await self._session.flush()

    async def _get_row(self, user_id: str, provider_message_id: str) -> EmailMessageRow | None:
        result = await self._session.execute(
            select(EmailMessageRow).where(
                EmailMessageRow.user_id == user_id,
                EmailMessageRow.provider_message_id == provider_message_id,
            )
        )
        return result.scalar_one_or_none()
