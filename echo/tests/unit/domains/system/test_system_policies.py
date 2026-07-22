from datetime import UTC, datetime

from domains.system.models import MonitorType
from domains.system.policies import (
    calendar_conflict_dedup_key,
    find_calendar_conflicts,
    integration_failure_dedup_key,
    ips_concentration_breach_dedup_key,
    is_within_quiet_hours,
    material_portfolio_news_dedup_key,
    stale_schwab_sync_dedup_key,
)
from domains.system.schemas import MonitorDefinition


def _monitor(**overrides: object) -> MonitorDefinition:
    defaults: dict[str, object] = {
        "user_id": "user_1",
        "monitor_type": MonitorType.CALENDAR_CONFLICT,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return MonitorDefinition(**defaults)  # type: ignore[arg-type]


def test_find_calendar_conflicts_detects_overlap() -> None:
    events = [
        (
            "event_a",
            datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        ),
        (
            "event_b",
            datetime(2026, 1, 1, 9, 30, tzinfo=UTC),
            datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        ),
    ]
    conflicts = find_calendar_conflicts(events)
    assert conflicts == [("event_a", "event_b")]


def test_find_calendar_conflicts_back_to_back_is_not_a_conflict() -> None:
    events = [
        (
            "event_a",
            datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        ),
        (
            "event_b",
            datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        ),
    ]
    assert find_calendar_conflicts(events) == []


def test_find_calendar_conflicts_no_overlap() -> None:
    events = [
        (
            "event_a",
            datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        ),
        (
            "event_b",
            datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 13, 0, tzinfo=UTC),
        ),
    ]
    assert find_calendar_conflicts(events) == []


def test_calendar_conflict_dedup_key_is_order_independent() -> None:
    assert calendar_conflict_dedup_key("a", "b") == calendar_conflict_dedup_key("b", "a")


def test_is_within_quiet_hours_simple_window() -> None:
    monitor = _monitor(quiet_hours_start_utc=22, quiet_hours_end_utc=7)
    assert is_within_quiet_hours(monitor, datetime(2026, 1, 1, 23, 0, tzinfo=UTC)) is True
    assert is_within_quiet_hours(monitor, datetime(2026, 1, 1, 3, 0, tzinfo=UTC)) is True
    assert is_within_quiet_hours(monitor, datetime(2026, 1, 1, 12, 0, tzinfo=UTC)) is False


def test_is_within_quiet_hours_non_wrapping_window() -> None:
    monitor = _monitor(quiet_hours_start_utc=9, quiet_hours_end_utc=17)
    assert is_within_quiet_hours(monitor, datetime(2026, 1, 1, 12, 0, tzinfo=UTC)) is True
    assert is_within_quiet_hours(monitor, datetime(2026, 1, 1, 20, 0, tzinfo=UTC)) is False


def test_is_within_quiet_hours_none_when_not_configured() -> None:
    monitor = _monitor(quiet_hours_start_utc=None, quiet_hours_end_utc=None)
    assert is_within_quiet_hours(monitor, datetime(2026, 1, 1, 3, 0, tzinfo=UTC)) is False


def test_dedup_key_builders_are_deterministic_and_distinct() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert stale_schwab_sync_dedup_key("user_1", now) == stale_schwab_sync_dedup_key("user_1", now)
    assert ips_concentration_breach_dedup_key(
        "user_1", "max_position_percent", "AAPL over limit"
    ) != ips_concentration_breach_dedup_key("user_1", "max_position_percent", "MSFT over limit")
    assert material_portfolio_news_dedup_key(
        "user_1", "digest_1"
    ) != material_portfolio_news_dedup_key("user_1", "digest_2")
    assert integration_failure_dedup_key("user_1", "Schwab", now) != integration_failure_dedup_key(
        "user_1", "Google Calendar", now
    )
