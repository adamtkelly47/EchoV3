from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.calendar.models import EventStatus
from domains.calendar.repository import (
    PostgresCalendarCredentialRepository,
    PostgresCalendarEventRepository,
)
from domains.calendar.schemas import CalendarCredential, CalendarEvent


async def test_credential_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresCalendarCredentialRepository(db_session)
    credential = CalendarCredential(
        user_id="user_1",
        encrypted_access_token="enc-access",
        encrypted_refresh_token="enc-refresh",
        access_token_expires_at=datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC),
        scope="https://www.googleapis.com/auth/calendar.readonly",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    await repo.save(credential)
    restored = await repo.get_for_user("user_1")

    assert restored is not None
    assert restored.encrypted_access_token == "enc-access"
    assert restored.scope == "https://www.googleapis.com/auth/calendar.readonly"


async def test_credential_save_updates_existing_rather_than_duplicating(
    db_session: AsyncSession,
) -> None:
    repo = PostgresCalendarCredentialRepository(db_session)
    original = CalendarCredential(
        user_id="user_1",
        encrypted_access_token="enc-access-v1",
        encrypted_refresh_token="enc-refresh",
        access_token_expires_at=datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC),
        scope="scope",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save(original)

    refreshed = original.model_copy(
        update={
            "encrypted_access_token": "enc-access-v2",
            "updated_at": datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC),
        }
    )
    await repo.save(refreshed)

    restored = await repo.get_for_user("user_1")
    assert restored is not None
    assert restored.encrypted_access_token == "enc-access-v2"


async def test_event_upsert_dedups_by_provider_event_id(db_session: AsyncSession) -> None:
    repo = PostgresCalendarEventRepository(db_session)
    event = CalendarEvent(
        user_id="user_1",
        provider_event_id="google-event-1",
        calendar_id="primary",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, 0, tzinfo=UTC),
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.upsert_many([event])

    updated = event.model_copy(
        update={"summary": "Standup (moved)", "synced_at": datetime(2026, 1, 1, 1, tzinfo=UTC)}
    )
    await repo.upsert_many([updated])

    results = await repo.list_in_range(
        "user_1", "primary", datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)
    )
    assert len(results) == 1
    assert results[0].summary == "Standup (moved)"


async def test_list_in_range_filters_by_overlap_not_containment(db_session: AsyncSession) -> None:
    repo = PostgresCalendarEventRepository(db_session)
    inside = CalendarEvent(
        user_id="user_1",
        provider_event_id="inside",
        calendar_id="primary",
        summary="Inside range",
        start=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, 0, tzinfo=UTC),
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    outside = CalendarEvent(
        user_id="user_1",
        provider_event_id="outside",
        calendar_id="primary",
        summary="Outside range",
        start=datetime(2026, 2, 1, 9, 0, 0, tzinfo=UTC),
        end=datetime(2026, 2, 1, 9, 15, 0, tzinfo=UTC),
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.upsert_many([inside, outside])

    results = await repo.list_in_range(
        "user_1", "primary", datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)
    )
    assert [r.provider_event_id for r in results] == ["inside"]


async def test_get_event_by_provider_id(db_session: AsyncSession) -> None:
    repo = PostgresCalendarEventRepository(db_session)
    event = CalendarEvent(
        user_id="user_1",
        provider_event_id="google-event-2",
        calendar_id="primary",
        summary="1:1",
        status=EventStatus.TENTATIVE,
        start=datetime(2026, 1, 2, 14, 0, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 14, 30, 0, tzinfo=UTC),
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.upsert_many([event])

    result = await repo.get("user_1", "google-event-2")
    assert result is not None
    assert result.status == EventStatus.TENTATIVE
