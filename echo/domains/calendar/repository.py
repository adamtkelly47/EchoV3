"""Calendar owns its own persistence — credentials and cached events are
domain-owned aggregates (Docs/DOMAIN_OWNERSHIP.md: "Calendar repositories
own: events / availability / preferences / reminders / sync metadata"), so
the ORM tables live here rather than under infrastructure/database/tables/
— matching the Approvals (Phase 6), Conversation (Phase 8), and Memory
(Phase 9) precedent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import Boolean, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.calendar.models import EventStatus
from domains.calendar.schemas import CalendarCredential, CalendarEvent
from infrastructure.database.base import Base


class CalendarCredentialRow(Base):
    __tablename__ = "calendar_credentials"

    credential_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    provider: Mapped[str] = mapped_column(String)
    encrypted_access_token: Mapped[str] = mapped_column(String)
    encrypted_refresh_token: Mapped[str] = mapped_column(String)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarEventRow(Base):
    __tablename__ = "calendar_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    provider_event_id: Mapped[str] = mapped_column(String, index=True)
    calendar_id: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    all_day: Mapped[bool] = mapped_column(Boolean)
    timezone: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    is_busy: Mapped[bool] = mapped_column(Boolean)
    recurring_event_id: Mapped[str | None] = mapped_column(String)
    html_link: Mapped[str | None] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _event_to_row(event: CalendarEvent) -> CalendarEventRow:
    return CalendarEventRow(
        event_id=event.event_id,
        user_id=event.user_id,
        provider_event_id=event.provider_event_id,
        calendar_id=event.calendar_id,
        summary=event.summary,
        description=event.description,
        start=event.start,
        end=event.end,
        all_day=event.all_day,
        timezone=event.timezone,
        status=event.status.value,
        is_busy=event.is_busy,
        recurring_event_id=event.recurring_event_id,
        html_link=event.html_link,
        synced_at=event.synced_at,
    )


def _row_to_event(row: CalendarEventRow) -> CalendarEvent:
    return CalendarEvent(
        event_id=row.event_id,
        user_id=row.user_id,
        provider_event_id=row.provider_event_id,
        calendar_id=row.calendar_id,
        summary=row.summary,
        description=row.description,
        start=row.start,
        end=row.end,
        all_day=row.all_day,
        timezone=row.timezone,
        status=EventStatus(row.status),
        is_busy=row.is_busy,
        recurring_event_id=row.recurring_event_id,
        html_link=row.html_link,
        synced_at=row.synced_at,
    )


class CalendarCredentialRepository(Protocol):
    async def save(self, credential: CalendarCredential) -> None: ...
    async def get_for_user(self, user_id: str) -> CalendarCredential | None: ...


class CalendarEventRepository(Protocol):
    async def upsert_many(self, events: list[CalendarEvent]) -> None: ...
    async def list_in_range(
        self, user_id: str, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[CalendarEvent]: ...
    async def get(self, user_id: str, provider_event_id: str) -> CalendarEvent | None: ...


class PostgresCalendarCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, credential: CalendarCredential) -> None:
        existing = await self._get_row(credential.user_id)
        if existing is None:
            self._session.add(
                CalendarCredentialRow(
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

    async def get_for_user(self, user_id: str) -> CalendarCredential | None:
        row = await self._get_row(user_id)
        if row is None:
            return None
        return CalendarCredential(
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

    async def _get_row(self, user_id: str) -> CalendarCredentialRow | None:
        result = await self._session.execute(
            select(CalendarCredentialRow).where(CalendarCredentialRow.user_id == user_id)
        )
        return result.scalar_one_or_none()


class PostgresCalendarEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, events: list[CalendarEvent]) -> None:
        for event in events:
            result = await self._session.execute(
                select(CalendarEventRow).where(
                    CalendarEventRow.user_id == event.user_id,
                    CalendarEventRow.provider_event_id == event.provider_event_id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                self._session.add(_event_to_row(event))
            else:
                self._update_row(existing, event)
        await self._session.flush()

    def _update_row(self, row: CalendarEventRow, event: CalendarEvent) -> None:
        row.summary = event.summary
        row.description = event.description
        row.start = event.start
        row.end = event.end
        row.all_day = event.all_day
        row.timezone = event.timezone
        row.status = event.status.value
        row.is_busy = event.is_busy
        row.recurring_event_id = event.recurring_event_id
        row.html_link = event.html_link
        row.synced_at = event.synced_at

    async def list_in_range(
        self, user_id: str, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[CalendarEvent]:
        result = await self._session.execute(
            select(CalendarEventRow)
            .where(
                CalendarEventRow.user_id == user_id,
                CalendarEventRow.calendar_id == calendar_id,
                CalendarEventRow.start < time_max,
                CalendarEventRow.end > time_min,
            )
            .order_by(CalendarEventRow.start.asc())
        )
        return [_row_to_event(row) for row in result.scalars().all()]

    async def get(self, user_id: str, provider_event_id: str) -> CalendarEvent | None:
        result = await self._session.execute(
            select(CalendarEventRow).where(
                CalendarEventRow.user_id == user_id,
                CalendarEventRow.provider_event_id == provider_event_id,
            )
        )
        row = result.scalar_one_or_none()
        return _row_to_event(row) if row is not None else None
