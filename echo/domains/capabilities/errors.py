"""Capabilities-specific errors. Reuses core.errors' taxonomy for anything
generic (ValidationError, AuthorizationError, EchoTimeoutError, ...) — only
adds what's genuinely specific to this domain, per CONSTITUTION.md's
Duplicate Business Rules prohibition.
"""

from core.errors import EchoError, Severity


class CapabilityNotFoundError(EchoError):
    code = "capability_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class CapabilityAlreadyRegisteredError(EchoError):
    code = "capability_already_registered"
    retryable = False
    severity = Severity.HIGH
    http_status = 409


class WriteCapabilityNotExecutableError(EchoError):
    """Write capabilities may be registered (their contract exists) but not
    executed until the Approval Engine exists (Phase 6) — CONSTITUTION.md:
    "No write capability may precede its corresponding read capability" and
    "Execution is owned by the Approval Engine.\" """

    code = "write_capability_requires_approval_engine"
    retryable = False
    severity = Severity.HIGH
    http_status = 403
