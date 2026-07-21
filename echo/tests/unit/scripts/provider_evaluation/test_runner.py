from scripts.provider_evaluation.clients import RawResponse
from scripts.provider_evaluation.metrics import Outcome
from scripts.provider_evaluation.runner import (
    auth_and_access_outcomes,
    field_completeness,
    latency_outcome,
    rate_limit_evidence,
)


def _response(**overrides: object) -> RawResponse:
    defaults: dict[str, object] = {
        "status_code": 200,
        "elapsed_ms": 100.0,
        "json_body": {"name": "Apple Inc"},
        "text_excerpt": "",
        "headers": {},
        "error": None,
    }
    defaults.update(overrides)
    return RawResponse(**defaults)  # type: ignore[arg-type]


def test_latency_outcome_thresholds() -> None:
    assert latency_outcome(500) == Outcome.PASS
    assert latency_outcome(3000) == Outcome.PARTIAL
    assert latency_outcome(9000) == Outcome.FAIL


def test_auth_and_access_outcomes_success() -> None:
    auth, access, evidence = auth_and_access_outcomes(_response())
    assert auth == Outcome.PASS
    assert access == Outcome.PASS
    assert "200" in evidence


def test_auth_and_access_outcomes_unauthorized() -> None:
    auth, access, _ = auth_and_access_outcomes(_response(status_code=401, json_body=None))
    assert auth == Outcome.FAIL
    assert access == Outcome.FAIL


def test_auth_and_access_outcomes_payment_required_is_a_real_auth_success_but_paywalled() -> None:
    """A key that authenticates but hits a paywalled endpoint is a distinct,
    real finding — not the same as an invalid key (PROMPT.md Phase 15: "Do
    not trust a provider's statement that a free tier exists unless an
    actual request succeeds")."""
    auth, access, _ = auth_and_access_outcomes(_response(status_code=402, json_body=None))
    assert auth == Outcome.PASS
    assert access == Outcome.FAIL


def test_auth_and_access_outcomes_detects_paywall_message_in_a_200_body() -> None:
    auth, access, evidence = auth_and_access_outcomes(
        _response(json_body={"error": "Upgrade your plan to access this endpoint"})
    )
    assert auth == Outcome.PASS
    assert access == Outcome.FAIL
    assert "paywall" in evidence.lower()


def test_auth_and_access_outcomes_empty_body_is_partial_access() -> None:
    auth, access, _ = auth_and_access_outcomes(_response(json_body=[]))
    assert auth == Outcome.PASS
    assert access == Outcome.PARTIAL


def test_auth_and_access_outcomes_transport_error() -> None:
    auth, access, evidence = auth_and_access_outcomes(
        _response(status_code=0, json_body=None, error="Connection timed out")
    )
    assert auth == Outcome.FAIL
    assert access == Outcome.FAIL
    assert "timed out" in evidence


def test_field_completeness_all_present() -> None:
    outcome, evidence = field_completeness({"a": 1, "b": 2}, ["a", "b"])
    assert outcome == Outcome.PASS
    assert "2/2" not in evidence  # phrased as "all N", not a fraction, when complete


def test_field_completeness_partial() -> None:
    outcome, evidence = field_completeness({"a": 1, "b": None}, ["a", "b", "c"])
    assert outcome == Outcome.PARTIAL
    assert "1/3" in evidence
    assert "b" in evidence and "c" in evidence


def test_field_completeness_none_present() -> None:
    outcome, _ = field_completeness({"x": 1}, ["a", "b"])
    assert outcome == Outcome.FAIL


def test_field_completeness_unwraps_a_list_of_objects() -> None:
    outcome, _ = field_completeness([{"a": 1, "b": 2}], ["a", "b"])
    assert outcome == Outcome.PASS


def test_rate_limit_evidence_observed() -> None:
    outcome, evidence = rate_limit_evidence(_response(headers={"X-RateLimit-Remaining": "59"}))
    assert outcome == Outcome.PASS
    assert "X-RateLimit-Remaining" in evidence


def test_rate_limit_evidence_not_observed() -> None:
    outcome, evidence = rate_limit_evidence(_response(headers={}))
    assert outcome == Outcome.PARTIAL
    assert "not observed" in evidence
