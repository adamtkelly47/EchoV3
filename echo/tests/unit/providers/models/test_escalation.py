from providers.models.contracts import TaskType
from providers.models.escalation import should_escalate


def test_conversation_always_escalates() -> None:
    assert should_escalate(TaskType.CONVERSATION) is True


def test_classification_stays_local_by_default() -> None:
    assert should_escalate(TaskType.CLASSIFICATION) is False


def test_failed_schema_validation_escalates() -> None:
    assert should_escalate(TaskType.CLASSIFICATION, schema_validation_failed=True) is True


def test_low_confidence_escalates() -> None:
    assert (
        should_escalate(TaskType.EXTRACTION, local_confidence=0.3, confidence_threshold=0.6) is True
    )


def test_high_confidence_stays_local() -> None:
    assert (
        should_escalate(TaskType.EXTRACTION, local_confidence=0.9, confidence_threshold=0.6)
        is False
    )


def test_consequential_task_escalates() -> None:
    assert should_escalate(TaskType.SUMMARIZATION, is_consequential=True) is True
