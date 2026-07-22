from core.errors import EchoError, Severity


class SchwabCredentialNotFoundError(EchoError):
    code = "schwab_credential_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class SchwabTokenRefreshError(EchoError):
    code = "schwab_token_refresh_failed"
    retryable = False
    severity = Severity.HIGH
    http_status = 502


class SchwabReauthorizationRequiredError(EchoError):
    """Schwab's refresh token itself has passed its 7-day hard expiry — no
    amount of retrying will refresh it; the user must redo the full OAuth
    consent flow. Distinct from SchwabTokenRefreshError (a transient/provider
    failure) so callers can distinguish "try again" from "reconnect.\" """

    code = "schwab_reauthorization_required"
    retryable = False
    severity = Severity.HIGH
    http_status = 401


class SchwabOAuthStateInvalidError(EchoError):
    code = "schwab_oauth_state_invalid"
    retryable = False
    severity = Severity.HIGH
    http_status = 400


class SchwabRedirectValueInvalidError(EchoError):
    """The pasted post-consent value (full dead-page URL or bare code) had
    no extractable `code` — a malformed paste, not a provider failure."""

    code = "schwab_redirect_value_invalid"
    retryable = False
    severity = Severity.LOW
    http_status = 400


class SchwabAccountNotFoundError(EchoError):
    code = "schwab_account_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class PortfolioSnapshotNotFoundError(EchoError):
    """Raised by the Phase 13 dashboard calculations when no sync has ever
    completed for this user — there is deliberately no fallback to
    live-computing a snapshot on the fly (PROMPT.md Phase 13 verification 1:
    "every displayed number traces to snapshot records"), only ever the
    last immutable one `POST /portfolio/sync` produced."""

    code = "portfolio_snapshot_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class NoActiveIPSError(EchoError):
    """Compliance evaluation (PROMPT.md Phase 14) requires a written,
    versioned strategy document to evaluate against — there is deliberately
    no implicit default policy to fall back to."""

    code = "no_active_ips"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class IPSValidationError(EchoError):
    """A malformed IPS edit (e.g. an allocation range with min > max) — a
    user input error, not a provider or system failure."""

    code = "ips_validation_failed"
    retryable = False
    severity = Severity.LOW
    http_status = 400


class HypotheticalTradeNotFoundError(EchoError):
    code = "hypothetical_trade_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class HypotheticalTradeAlreadyClosedError(EchoError):
    """PROMPT.md Phase 27 capability 8: a review is a one-time, terminal
    event — mirrors domains/system/errors.py's own
    HallucinationIncidentAlreadyResolvedError precedent."""

    code = "hypothetical_trade_already_closed"
    retryable = False
    severity = Severity.LOW
    http_status = 409


class QuotePriceUnavailableError(EchoError):
    """A hypothetical trade needs a real reference price at proposal time
    and at every performance sample — this codebase never invents or
    estimates one when the provider returns none."""

    code = "quote_price_unavailable"
    retryable = True
    severity = Severity.MEDIUM
    http_status = 502
