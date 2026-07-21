"""Structured logging (CONSTITUTION.md: "Logs exist for engineers. Responses
exist for users."). Every log record automatically carries the current
correlation id (core/observability/correlation.py) so a single request's or
job's full execution can be reconstructed from logs alone.

This is the only place `logging.basicConfig`-equivalent setup happens —
apps call `configure_logging()` once at startup rather than configuring
logging themselves.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from core.observability.correlation import get_correlation_id


class _CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    """Configures the root logger with structured JSON output and
    correlation-id injection. Call once at process startup."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_StructuredFormatter())
    handler.addFilter(_CorrelationFilter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
