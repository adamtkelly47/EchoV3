from core.errors import EchoError, Severity


class EmailCredentialNotFoundError(EchoError):
    """No stored OAuth credential for this user — they haven't completed
    the Gmail OAuth flow yet."""

    code = "email_credential_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class EmailTokenRefreshError(EchoError):
    """The refresh token was rejected by the provider (e.g. revoked
    consent) — surfaced honestly (PROMPT.md Phase 20 verification pattern,
    matching Calendar's Phase 10) rather than silently retried forever."""

    code = "email_token_refresh_failed"
    retryable = False
    severity = Severity.HIGH
    http_status = 502


class EmailOAuthStateInvalidError(EchoError):
    """The OAuth callback's `state` parameter failed signature or freshness
    verification (Docs/SECURITY.md: "Redirect target validation on OAuth
    callback flows") — rejected as a possible CSRF attempt, not retried."""

    code = "email_oauth_state_invalid"
    retryable = False
    severity = Severity.HIGH
    http_status = 400


class EmailMessageNotFoundError(EchoError):
    """Requested message id has no cached record and the provider had
    nothing at that id either."""

    code = "email_message_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404
