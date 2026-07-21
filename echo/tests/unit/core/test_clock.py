from datetime import UTC, datetime, timedelta

from core.time.clock import FakeClock, SystemClock, is_fresh


def test_fake_clock_does_not_advance_on_its_own() -> None:
    clock = FakeClock(initial=datetime(2026, 1, 1, tzinfo=UTC))
    first = clock.now_utc()
    second = clock.now_utc()
    assert first == second == datetime(2026, 1, 1, tzinfo=UTC)


def test_fake_clock_advance_moves_time_forward() -> None:
    clock = FakeClock(initial=datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(timedelta(hours=1))
    assert clock.now_utc() == datetime(2026, 1, 1, 1, 0, 0, tzinfo=UTC)


def test_fake_clock_monotonic_tracks_advances() -> None:
    clock = FakeClock()
    start = clock.monotonic()
    clock.advance(timedelta(seconds=5))
    assert clock.monotonic() == start + 5.0


def test_system_clock_now_utc_has_utc_tzinfo() -> None:
    clock = SystemClock()
    assert clock.now_utc().tzinfo is UTC


def test_is_fresh_within_max_age() -> None:
    clock = FakeClock(initial=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    observed_at = datetime(2026, 1, 1, 11, 55, 0, tzinfo=UTC)
    assert is_fresh(observed_at, timedelta(minutes=10), clock) is True


def test_is_fresh_outside_max_age() -> None:
    clock = FakeClock(initial=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    observed_at = datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC)
    assert is_fresh(observed_at, timedelta(minutes=10), clock) is False
