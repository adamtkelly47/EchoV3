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


class NoDigestAvailableError(EchoError):
    """PROMPT.md Phase 17: a digest requires a completed news-intelligence
    run (application/orchestrators/news_intelligence.py) — there is
    deliberately no fallback to computing one on the fly from a read
    endpoint, same discipline as Portfolio's dashboard/snapshot split."""

    code = "no_digest_available"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class InsiderNotFoundError(EchoError):
    """PROMPT.md Phase 18: no ingested transaction history exists for this
    (issuer, insider) pair — distinct from an empty-but-valid history,
    which `domains.research.policies.compute_insider_profile` handles by
    simply returning `None` rather than raising."""

    code = "insider_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class PoliticianNotFoundError(EchoError):
    """PROMPT.md Phase 19: no ingested PTR transaction history exists for
    this `politician_bioguide_id` — mirrors `InsiderNotFoundError`."""

    code = "politician_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404
