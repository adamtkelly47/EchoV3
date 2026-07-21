from core.errors import EchoError, Severity


class ProposalNotFoundError(EchoError):
    code = "proposal_not_found"
    retryable = False
    severity = Severity.LOW
    http_status = 404


class InvalidStateTransitionError(EchoError):
    code = "invalid_state_transition"
    retryable = False
    severity = Severity.HIGH
    http_status = 409


class PayloadMismatchError(EchoError):
    """The approved payload hash no longer matches the proposal's current
    payload — CONSTITUTION.md: "Any material modification to an approved
    proposal SHALL invalidate the previous approval.\" """

    code = "payload_mismatch"
    retryable = False
    severity = Severity.HIGH
    http_status = 409


class SelfApprovalNotAllowedError(EchoError):
    """CONSTITUTION.md: "Echo shall never approve its own proposals.\" """

    code = "self_approval_not_allowed"
    retryable = False
    severity = Severity.CRITICAL
    http_status = 403


class NoApprovalOnRecordError(EchoError):
    code = "no_approval_on_record"
    retryable = False
    severity = Severity.HIGH
    http_status = 404
