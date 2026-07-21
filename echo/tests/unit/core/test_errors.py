import pytest

from core.errors import EchoError, Severity, ValidationError


def test_error_carries_code_message_and_severity() -> None:
    error = ValidationError("bad input")
    assert error.code == "validation_error"
    assert error.message == "bad input"
    assert error.severity == Severity.LOW


def test_error_detail_is_optional_and_separate_from_message() -> None:
    error = ValidationError("bad input", detail="field 'x' was negative")
    assert error.message == "bad input"
    assert error.detail == "field 'x' was negative"


def test_error_is_a_real_exception() -> None:
    with pytest.raises(ValidationError):
        raise ValidationError("bad input")


def test_subclasses_have_distinct_stable_codes() -> None:
    codes = {cls.code for cls in EchoError.__subclasses__()}
    assert len(codes) == len(EchoError.__subclasses__()), "every error subclass needs a unique code"


def test_correlation_id_is_carried_when_supplied() -> None:
    error = ValidationError("bad input", correlation_id="corr_abc")
    assert error.correlation_id == "corr_abc"
