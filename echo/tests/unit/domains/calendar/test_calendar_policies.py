from datetime import UTC, datetime, timedelta

import pytest

from domains.calendar.errors import CalendarOAuthStateInvalidError
from domains.calendar.models import EventStatus
from domains.calendar.policies import (
    generate_oauth_state,
    is_recurring_instance,
    is_stale,
    needs_refresh,
    parse_calendar_list,
    parse_event,
    parse_event_datetime,
    parse_event_status,
    parse_free_busy,
    parse_is_busy,
    verify_oauth_state,
)
from domains.calendar.schemas import CalendarCredential


def _credential(**overrides: object) -> CalendarCredential:
    defaults: dict[str, object] = {
        "user_id": "user_1",
        "encrypted_access_token": "enc-access",
        "encrypted_refresh_token": "enc-refresh",
        "access_token_expires_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "scope": "https://www.googleapis.com/auth/calendar.readonly",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return CalendarCredential(**defaults)  # type: ignore[arg-type]


def test_needs_refresh_true_within_buffer_of_expiry() -> None:
    credential = _credential(access_token_expires_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    assert not needs_refresh(credential, datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC))
    assert needs_refresh(credential, datetime(2026, 1, 1, 11, 56, 0, tzinfo=UTC))


def test_is_recurring_instance() -> None:
    assert is_recurring_instance("recurring_abc")
    assert not is_recurring_instance(None)


def test_is_stale() -> None:
    synced_at = datetime(2026, 1, 1, tzinfo=UTC)
    assert not is_stale(synced_at, synced_at + timedelta(minutes=1), timedelta(minutes=5))
    assert is_stale(synced_at, synced_at + timedelta(minutes=10), timedelta(minutes=5))


def test_parse_event_datetime_timed() -> None:
    dt, all_day, tz = parse_event_datetime(
        {"dateTime": "2026-03-15T09:30:00-07:00", "timeZone": "America/Los_Angeles"}
    )
    assert dt == datetime(2026, 3, 15, 16, 30, 0, tzinfo=UTC)
    assert all_day is False
    assert tz == "America/Los_Angeles"


def test_parse_event_datetime_all_day() -> None:
    dt, all_day, tz = parse_event_datetime({"date": "2026-03-15"})
    assert dt == datetime(2026, 3, 15, tzinfo=UTC)
    assert all_day is True
    assert tz is None


def test_parse_event_status_falls_back_to_confirmed_on_unknown_value() -> None:
    assert parse_event_status({"status": "confirmed"}) == EventStatus.CONFIRMED
    assert parse_event_status({"status": "tentative"}) == EventStatus.TENTATIVE
    assert parse_event_status({"status": "some_future_google_status"}) == EventStatus.CONFIRMED
    assert parse_event_status({}) == EventStatus.CONFIRMED


def test_parse_is_busy() -> None:
    assert parse_is_busy({"transparency": "opaque"}) is True
    assert parse_is_busy({}) is True  # opaque is Google's own default
    assert parse_is_busy({"transparency": "transparent"}) is False


def test_parse_event_full_translation() -> None:
    raw = {
        "id": "abc123",
        "summary": "Team sync",
        "description": "Weekly sync",
        "start": {"dateTime": "2026-03-15T09:30:00Z"},
        "end": {"dateTime": "2026-03-15T10:00:00Z"},
        "status": "confirmed",
        "transparency": "opaque",
        "recurringEventId": "parent-event-id",
        "htmlLink": "https://calendar.google.com/event?eid=abc123",
    }
    event = parse_event(
        raw, user_id="user_1", calendar_id="primary", synced_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert event.provider_event_id == "abc123"
    assert event.summary == "Team sync"
    assert event.start == datetime(2026, 3, 15, 9, 30, 0, tzinfo=UTC)
    assert event.all_day is False
    assert event.is_busy is True
    assert event.recurring_event_id == "parent-event-id"
    assert event.html_link == "https://calendar.google.com/event?eid=abc123"


def test_parse_event_missing_summary_defaults_to_placeholder() -> None:
    raw = {
        "id": "abc123",
        "start": {"date": "2026-03-15"},
        "end": {"date": "2026-03-16"},
    }
    event = parse_event(
        raw, user_id="user_1", calendar_id="primary", synced_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert event.summary == "(no title)"
    assert event.all_day is True


def test_parse_free_busy() -> None:
    raw = {
        "calendars": {
            "primary": {"busy": [{"start": "2026-01-01T09:00:00Z", "end": "2026-01-01T10:00:00Z"}]}
        }
    }
    periods = parse_free_busy(raw, "primary")
    assert len(periods) == 1
    assert periods[0].start == datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
    assert periods[0].end == datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)


def test_parse_free_busy_unknown_calendar_returns_empty() -> None:
    assert parse_free_busy({"calendars": {}}, "primary") == []


def test_parse_calendar_list() -> None:
    raw = {
        "items": [
            {"id": "primary", "summary": "user@example.com", "primary": True, "timeZone": "UTC"},
            {"id": "other-cal", "summary": "Team calendar"},
        ]
    }
    calendars = parse_calendar_list(raw)
    assert len(calendars) == 2
    assert calendars[0].primary is True
    assert calendars[1].primary is False
    assert calendars[1].time_zone is None


def test_generate_and_verify_oauth_state_round_trips() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-abc", now, "test-secret")
    recovered_user_id = verify_oauth_state(state, "test-secret", now + timedelta(minutes=1))
    assert recovered_user_id == "user_1"


def test_verify_oauth_state_rejects_wrong_secret() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-abc", now, "correct-secret")
    with pytest.raises(CalendarOAuthStateInvalidError):
        verify_oauth_state(state, "wrong-secret", now)


def test_verify_oauth_state_rejects_tampered_payload() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-abc", now, "test-secret")
    tampered = state[:-4] + "abcd"
    with pytest.raises(CalendarOAuthStateInvalidError):
        verify_oauth_state(tampered, "test-secret", now)


def test_verify_oauth_state_rejects_expired_state() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce-abc", now, "test-secret")
    with pytest.raises(CalendarOAuthStateInvalidError):
        verify_oauth_state(state, "test-secret", now + timedelta(minutes=11))


def test_verify_oauth_state_rejects_malformed_state() -> None:
    with pytest.raises(CalendarOAuthStateInvalidError):
        verify_oauth_state("not-valid-base64!!!", "test-secret", datetime(2026, 1, 1, tzinfo=UTC))
