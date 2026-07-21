"""Every request gets a correlation identifier that stays attached to logs,
provider calls, events, capability execution, approval records, and audit
entries (CONSTITUTION.md: Correlation IDs). Implemented with a contextvar so
it propagates automatically through async call chains without being threaded
through every function signature.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from core.identifiers import new_id

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """The correlation id for the current async context, or None if no
    scope has been entered (e.g. code running outside a request/job)."""
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None) -> Iterator[str]:
    """Enters a correlation scope for the duration of the `with` block.
    Generates a new id if one isn't supplied (the common case: a new
    request or job starting).
    """
    value = correlation_id or new_id("corr")
    token = _correlation_id.set(value)
    try:
        yield value
    finally:
        _correlation_id.reset(token)
