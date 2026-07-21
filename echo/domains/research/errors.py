from core.errors import EchoError, Severity


class IssuerNotFoundError(EchoError):
    code = "issuer_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class NoProviderDataAvailableError(EchoError):
    """Every configured provider failed or returned nothing for this ticker
    — distinct from a single provider failing (which is recorded as a
    per-provider warning and doesn't block ingestion from the others,
    PROMPT.md Phase 16 implement item 10: "provider fallback rules")."""

    code = "no_provider_data_available"
    retryable = True
    severity = Severity.LOW
    http_status = 502
