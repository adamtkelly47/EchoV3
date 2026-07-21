from core.errors import EchoError, Severity


class SessionNotFoundError(EchoError):
    code = "session_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404
