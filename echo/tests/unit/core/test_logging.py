import json
import logging

from core.logging.setup import _CorrelationFilter, _StructuredFormatter
from core.observability.correlation import correlation_scope


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_structured_formatter_produces_valid_json() -> None:
    record = _make_record("hello")
    formatted = _StructuredFormatter().format(record)
    payload = json.loads(formatted)
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"


def test_correlation_filter_attaches_current_correlation_id() -> None:
    record = _make_record("hello")
    with correlation_scope("corr_test"):
        _CorrelationFilter().filter(record)
    assert record.correlation_id == "corr_test"  # type: ignore[attr-defined]


def test_correlation_filter_attaches_none_outside_a_scope() -> None:
    record = _make_record("hello")
    _CorrelationFilter().filter(record)
    assert record.correlation_id is None  # type: ignore[attr-defined]
