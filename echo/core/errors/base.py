"""Common error taxonomy (CONSTITUTION.md: "Errors should be categorized...
Errors should remain meaningful. Generic exceptions should be minimized.").

Every EchoError carries: a stable machine-readable code, a safe user-facing
message, optional internal diagnostic detail (never shown to the user),
a retry classification, a severity, and a correlation id for tracing the
error back through logs/audit. Domains raise the specific subclass that
matches what happened — not a bare `Exception` or a generic `EchoError`.
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EchoError(Exception):
    """Base class for every error Echo raises deliberately. Do not raise this
    directly — raise the specific subclass for what happened."""

    code: str = "unexpected_error"
    retryable: bool = False
    severity: Severity = Severity.MEDIUM
    http_status: int = 500
    """The HTTP status apps/api's global exception handler responds with —
    declared per-subclass like `code`/`retryable`/`severity`, so a route
    handler never has to know or guess how to translate a domain error into
    a wire response (PROMPT.md Phase 10 verification: "read failures are
    surfaced honestly" — a bare 500 with no body is not honest about *why*
    a request failed)."""

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.correlation_id = correlation_id

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ValidationError(EchoError):
    code = "validation_error"
    retryable = False
    severity = Severity.LOW
    http_status = 400


class AuthenticationError(EchoError):
    code = "authentication_error"
    retryable = False
    severity = Severity.HIGH
    http_status = 401


class AuthorizationError(EchoError):
    code = "authorization_error"
    retryable = False
    severity = Severity.HIGH
    http_status = 403


class ProviderUnavailableError(EchoError):
    code = "provider_unavailable"
    retryable = True
    severity = Severity.MEDIUM
    http_status = 502


class EchoTimeoutError(EchoError):
    code = "timeout_error"
    retryable = True
    severity = Severity.MEDIUM
    http_status = 504


class RateLimitedError(EchoError):
    code = "rate_limited"
    retryable = True
    severity = Severity.LOW
    http_status = 429


class ConfigurationError(EchoError):
    code = "configuration_error"
    retryable = False
    severity = Severity.CRITICAL
    http_status = 500


class ExecutionError(EchoError):
    code = "execution_error"
    retryable = False
    severity = Severity.HIGH
    http_status = 500


class UnexpectedError(EchoError):
    code = "unexpected_error"
    retryable = False
    severity = Severity.HIGH
    http_status = 500


class ApprovalRequiredError(EchoError):
    code = "approval_required"
    retryable = False
    severity = Severity.MEDIUM
    http_status = 403


class ApprovalExpiredError(EchoError):
    code = "approval_expired"
    retryable = False
    severity = Severity.MEDIUM
    http_status = 409


class ProposalChangedError(EchoError):
    code = "proposal_changed"
    retryable = False
    severity = Severity.MEDIUM
    http_status = 409


class ExecutionUncertainError(EchoError):
    """The system cannot confirm whether a write actually took effect
    externally — never silently treated as success or failure."""

    code = "execution_uncertain"
    retryable = False
    severity = Severity.HIGH
    http_status = 500


class VerificationFailedError(EchoError):
    code = "verification_failed"
    retryable = False
    severity = Severity.HIGH
    http_status = 500


class RetryExhaustedError(EchoError):
    code = "retry_exhausted"
    retryable = False
    severity = Severity.MEDIUM
    http_status = 503


class SchemaMismatchError(EchoError):
    code = "schema_mismatch"
    retryable = False
    severity = Severity.HIGH
    http_status = 500


class ModelOutputInvalidError(EchoError):
    """A language model's structured output failed schema validation. Per
    CONSTITUTION.md, this must never be silently coerced into valid data."""

    code = "model_output_invalid"
    retryable = True
    severity = Severity.MEDIUM
    http_status = 502


class SourceStaleError(EchoError):
    code = "source_stale"
    retryable = False
    severity = Severity.LOW
    http_status = 409


class SourceIncompleteError(EchoError):
    code = "source_incomplete"
    retryable = False
    severity = Severity.LOW
    http_status = 409
