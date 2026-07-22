from datetime import UTC, datetime

from domains.approvals.models import RiskLevel
from domains.approvals.policies import build_spoken_summary
from domains.approvals.schemas import ActionProposal


def _proposal(**overrides: object) -> ActionProposal:
    defaults: dict[str, object] = {
        "user_id": "user_1",
        "action_type": "calendar.create_event",
        "action_schema_version": 1,
        "summary": "Create a meeting with the design team",
        "payload": {"title": "Design sync", "attendees": ["a@example.com", "b@example.com"]},
        "target_system": "google_calendar",
        "expected_effect": "a new calendar event is created",
        "risk_level": RiskLevel.MEDIUM,
        "required_permission": "calendar.write",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "expires_at": datetime(2026, 1, 2, tzinfo=UTC),
        "created_by": "system",
        "payload_hash": "hash",
    }
    defaults.update(overrides)
    return ActionProposal(**defaults)  # type: ignore[arg-type]


def test_spoken_summary_never_includes_the_structured_payload() -> None:
    """PROMPT.md Phase 26 implement item 6: the spoken summary must never
    read out structured payload data — that is what the full readable
    review (the ActionProposal object itself) is for."""
    proposal = _proposal()
    spoken = build_spoken_summary(proposal)
    assert "attendees" not in spoken
    assert "a@example.com" not in spoken


def test_spoken_summary_includes_the_risk_level_and_target_system() -> None:
    proposal = _proposal(risk_level=RiskLevel.HIGH, target_system="schwab")
    spoken = build_spoken_summary(proposal)
    assert "high-risk" in spoken
    assert "schwab" in spoken


def test_spoken_summary_includes_the_human_readable_summary_text() -> None:
    proposal = _proposal(summary="Create a meeting with the design team")
    spoken = build_spoken_summary(proposal)
    assert "Create a meeting with the design team" in spoken
