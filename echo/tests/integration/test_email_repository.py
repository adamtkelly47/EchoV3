from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.email.models import EmailCategory
from domains.email.repository import (
    PostgresEmailCredentialRepository,
    PostgresEmailMessageRepository,
)
from domains.email.schemas import EmailCredential, EmailMessage, MessageClassification


async def test_credential_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresEmailCredentialRepository(db_session)
    credential = EmailCredential(
        user_id="user_1",
        encrypted_access_token="enc-access",
        encrypted_refresh_token="enc-refresh",
        access_token_expires_at=datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC),
        scope="https://www.googleapis.com/auth/gmail.readonly",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    await repo.save(credential)
    restored = await repo.get_for_user("user_1")

    assert restored is not None
    assert restored.encrypted_access_token == "enc-access"
    assert restored.scope == "https://www.googleapis.com/auth/gmail.readonly"


async def test_credential_save_updates_existing_rather_than_duplicating(
    db_session: AsyncSession,
) -> None:
    repo = PostgresEmailCredentialRepository(db_session)
    original = EmailCredential(
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


def _message(**overrides: object) -> EmailMessage:
    base = dict(
        user_id="user_1",
        provider_message_id="msg-1",
        thread_id="thread-1",
        subject="Hello",
        snippet="hi there",
        from_address="alice@example.com",
        to_addresses=["bob@example.com"],
        date=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        label_ids=["INBOX", "UNREAD"],
        is_unread=True,
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    base.update(overrides)
    return EmailMessage(**base)  # type: ignore[arg-type]


async def test_message_upsert_dedups_by_provider_message_id(db_session: AsyncSession) -> None:
    repo = PostgresEmailMessageRepository(db_session)
    message = _message()
    await repo.upsert_many([message])

    updated = message.model_copy(
        update={"subject": "Hello (edited)", "synced_at": datetime(2026, 1, 1, 1, tzinfo=UTC)}
    )
    await repo.upsert_many([updated])

    results = await repo.list_recent("user_1")
    assert len(results) == 1
    assert results[0].subject == "Hello (edited)"


async def test_list_recent_orders_newest_first(db_session: AsyncSession) -> None:
    repo = PostgresEmailMessageRepository(db_session)
    older = _message(provider_message_id="older", date=datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC))
    newer = _message(provider_message_id="newer", date=datetime(2026, 1, 3, 9, 0, 0, tzinfo=UTC))
    await repo.upsert_many([older, newer])

    results = await repo.list_recent("user_1", limit=10)

    assert [r.provider_message_id for r in results] == ["newer", "older"]


async def test_list_by_thread_orders_oldest_first(db_session: AsyncSession) -> None:
    repo = PostgresEmailMessageRepository(db_session)
    first = _message(
        provider_message_id="first",
        thread_id="thread-a",
        date=datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC),
    )
    second = _message(
        provider_message_id="second",
        thread_id="thread-a",
        date=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
    )
    await repo.upsert_many([first, second])

    results = await repo.list_by_thread("user_1", "thread-a")

    assert [r.provider_message_id for r in results] == ["first", "second"]


async def test_get_message_by_provider_id(db_session: AsyncSession) -> None:
    repo = PostgresEmailMessageRepository(db_session)
    message = _message(provider_message_id="get-me")
    await repo.upsert_many([message])

    result = await repo.get("user_1", "get-me")
    assert result is not None
    assert result.subject == "Hello"


async def test_save_classification_persists_and_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresEmailMessageRepository(db_session)
    message = _message(provider_message_id="classify-me")
    await repo.upsert_many([message])

    classification = MessageClassification(
        category=EmailCategory.ACTION_NEEDED,
        needs_response=True,
        action_items=["Reply with availability"],
        classified_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await repo.save_classification("user_1", "classify-me", classification)

    result = await repo.get("user_1", "classify-me")
    assert result is not None
    assert result.classification is not None
    assert result.classification.category == EmailCategory.ACTION_NEEDED
    assert result.classification.action_items == ["Reply with availability"]
