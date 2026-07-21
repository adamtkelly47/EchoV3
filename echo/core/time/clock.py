"""The platform's sole source of time (CONSTITUTION.md: "The platform owns
time. System time should never be read directly throughout the codebase.").
Business logic depends on the `Clock` protocol, never on `datetime.now()` or
`time.monotonic()` directly, so tests can substitute `FakeClock` for
deterministic behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from typing import Protocol


class Clock(Protocol):
    """Time source contract. Timestamps are stored in UTC; conversion to a
    user's local timezone happens only at the presentation boundary."""

    def now_utc(self) -> datetime:
        """Current time in UTC. This is the value stored and compared internally."""
        ...

    def now_local(self, tz: tzinfo) -> datetime:
        """Current time converted to the given timezone, for display only."""
        ...

    def monotonic(self) -> float:
        """Monotonic clock reading, for measuring elapsed durations (never for
        timestamps that need to be stored or compared across processes)."""
        ...


class SystemClock:
    """Real wall-clock time. The only place `datetime.now()`/`time.monotonic()`
    should be called directly in the entire codebase."""

    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def now_local(self, tz: tzinfo) -> datetime:
        return self.now_utc().astimezone(tz)

    def monotonic(self) -> float:
        import time

        return time.monotonic()


class FakeClock:
    """Deterministic clock for tests. Time only changes when explicitly
    advanced — never reads the real system clock. (Not named `TestClock`:
    pytest's default discovery treats any `Test*` class as a test case and
    warns when it can't collect one, since this class has an `__init__`.)"""

    def __init__(self, initial: datetime | None = None) -> None:
        self._current = initial or datetime(2026, 1, 1, tzinfo=UTC)
        self._monotonic = 0.0

    def now_utc(self) -> datetime:
        return self._current

    def now_local(self, tz: tzinfo) -> datetime:
        return self._current.astimezone(tz)

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, delta: timedelta) -> None:
        self._current += delta
        self._monotonic += delta.total_seconds()

    def set(self, when: datetime) -> None:
        self._current = when


def is_fresh(observed_at: datetime, max_age: timedelta, clock: Clock) -> bool:
    """Whether `observed_at` is within `max_age` of the clock's current time.
    Used to answer freshness questions (e.g. "is this portfolio snapshot
    stale?") without any domain reading the system clock itself.
    """
    return clock.now_utc() - observed_at <= max_age
