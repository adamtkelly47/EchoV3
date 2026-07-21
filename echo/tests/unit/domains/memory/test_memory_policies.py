from datetime import UTC, datetime, timedelta

from domains.memory.models import MemoryStatus
from domains.memory.policies import (
    clamp_confidence,
    conflicts_with,
    is_active,
    is_expired,
    is_valid_transition,
    rank_score,
)
from domains.memory.schemas import MemoryRecord


def _record(**overrides: object) -> MemoryRecord:
    defaults: dict[str, object] = {
        "user_id": "user_1",
        "subject_key": "user.favorite_color",
        "content": "The user's favorite color is blue.",
        "status": MemoryStatus.CONFIRMED,
        "confidence": 0.9,
        "source_type": "conversation",
        "source_id": "msg_1",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "confirmed_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return MemoryRecord(**defaults)  # type: ignore[arg-type]


def test_valid_transitions_from_candidate() -> None:
    assert is_valid_transition(MemoryStatus.CANDIDATE, MemoryStatus.CONFIRMED)
    assert is_valid_transition(MemoryStatus.CANDIDATE, MemoryStatus.DELETED)
    assert not is_valid_transition(MemoryStatus.CANDIDATE, MemoryStatus.SUPERSEDED)


def test_terminal_statuses_have_no_valid_transitions() -> None:
    for terminal in (MemoryStatus.SUPERSEDED, MemoryStatus.EXPIRED, MemoryStatus.DELETED):
        assert not is_valid_transition(terminal, MemoryStatus.CONFIRMED)


def test_clamp_confidence_bounds_to_zero_one() -> None:
    assert clamp_confidence(1.5) == 1.0
    assert clamp_confidence(-0.3) == 0.0
    assert clamp_confidence(0.42) == 0.42


def test_is_expired_true_once_past_expires_at() -> None:
    record = _record(expires_at=datetime(2026, 1, 2, tzinfo=UTC))
    assert not is_expired(record, datetime(2026, 1, 1, 12, tzinfo=UTC))
    assert is_expired(record, datetime(2026, 1, 2, 0, 0, 1, tzinfo=UTC))


def test_is_active_requires_confirmed_and_not_expired() -> None:
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert is_active(_record(status=MemoryStatus.CONFIRMED), now)
    assert not is_active(_record(status=MemoryStatus.CANDIDATE), now)
    assert not is_active(
        _record(status=MemoryStatus.CONFIRMED, expires_at=datetime(2026, 1, 1, tzinfo=UTC)), now
    )


def test_conflicts_with_detects_same_subject_different_content() -> None:
    existing = _record(content="The user's favorite color is blue.")
    assert conflicts_with(existing, "user.favorite_color", "The user's favorite color is green.")
    assert not conflicts_with(existing, "user.favorite_color", "The user's favorite color is blue.")
    assert not conflicts_with(existing, "user.favorite_food", "The user's favorite food is pizza.")


def test_conflicts_with_ignores_inactive_records() -> None:
    existing = _record(content="The user's favorite color is blue.", status=MemoryStatus.DELETED)
    assert not conflicts_with(
        existing, "user.favorite_color", "The user's favorite color is green."
    )


def test_rank_score_rewards_keyword_overlap_and_confidence() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    high_confidence = _record(content="The user's favorite color is blue.", confidence=0.9)
    low_confidence = _record(content="The user's favorite color is blue.", confidence=0.2)
    unrelated = _record(content="The user lives in Seattle.", confidence=0.9)

    terms = frozenset("what is the user's favorite color".split())
    assert rank_score(high_confidence, terms, now) > rank_score(low_confidence, terms, now)
    assert rank_score(high_confidence, terms, now) > rank_score(unrelated, terms, now)


def test_rank_score_recency_bonus_favors_recently_confirmed() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    recent = _record(confirmed_at=now - timedelta(days=1))
    old = _record(confirmed_at=now - timedelta(days=100))
    terms: frozenset[str] = frozenset()  # no keyword overlap either way

    assert rank_score(recent, terms, now) > rank_score(old, terms, now)
