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
