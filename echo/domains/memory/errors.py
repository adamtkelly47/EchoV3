from core.errors import EchoError, Severity


class MemoryNotFoundError(EchoError):
    code = "memory_not_found"
    retryable = False
    severity = Severity.LOW


class InvalidMemoryStateTransitionError(EchoError):
    code = "invalid_memory_state_transition"
    retryable = False
    severity = Severity.HIGH
