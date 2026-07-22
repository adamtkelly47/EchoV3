from core.errors import EchoError, Severity


class MonitorNotFoundError(EchoError):
    code = "monitor_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class AlertNotFoundError(EchoError):
    code = "alert_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class InvalidAlertTransitionError(EchoError):
    """An already-terminal alert (`ACKNOWLEDGED`/`SUPPRESSED`) cannot be
    acknowledged or suppressed again — mirrors domains/approvals/errors.py's
    own `InvalidStateTransitionError`."""

    code = "invalid_alert_transition"
    retryable = False
    severity = Severity.LOW
    http_status = 409


class HallucinationIncidentNotFoundError(EchoError):
    code = "hallucination_incident_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class HallucinationIncidentAlreadyResolvedError(EchoError):
    code = "hallucination_incident_already_resolved"
    retryable = False
    severity = Severity.LOW
    http_status = 409
