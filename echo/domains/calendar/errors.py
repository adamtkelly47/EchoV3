from core.errors import EchoError, Severity


class CalendarCredentialNotFoundError(EchoError):
    """No stored OAuth credential for this user — they haven't completed
    the Google OAuth flow yet."""

    code = "calendar_credential_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class CalendarTokenRefreshError(EchoError):
    """The refresh token was rejected by the provider (e.g. revoked
    consent) — surfaced honestly (PROMPT.md Phase 10 verification: "read
    failures are surfaced honestly") rather than silently retried forever."""

    code = "calendar_token_refresh_failed"
    retryable = False
    severity = Severity.HIGH
    http_status = 502


class CalendarOAuthStateInvalidError(EchoError):
    """The OAuth callback's `state` parameter failed signature or freshness
    verification (Docs/SECURITY.md: "Redirect target validation on OAuth
    callback flows") — rejected as a possible CSRF attempt, not retried."""

    code = "calendar_oauth_state_invalid"
    retryable = False
    severity = Severity.HIGH
    http_status = 400
