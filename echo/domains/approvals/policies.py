"""Policies decide; they never persist data (CONSTITUTION.md: Policy).
Payload hashing is the mechanism behind approval binding — CONSTITUTION.md:
"Any material modification to an approved proposal SHALL invalidate the
previous approval" is enforced by re-hashing and comparing, not by trusting
that nothing changed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from domains.approvals.models import VALID_TRANSITIONS, ProposalStatus
from domains.approvals.schemas import ActionProposal


def hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_valid_transition(current: ProposalStatus, target: ProposalStatus) -> bool:
    return target in VALID_TRANSITIONS[current]


def is_expired(expires_at: datetime, now: datetime) -> bool:
    return now >= expires_at


def payload_matches_approval(current_payload_hash: str, approved_payload_hash: str) -> bool:
    return current_payload_hash == approved_payload_hash


def build_spoken_summary(proposal: ActionProposal) -> str:
    """PROMPT.md Phase 26 implement item 6: "spoken summary versus full
    readable review distinction." Short and TTS-appropriate — never the
    structured `payload`/`warnings`, which is exactly what the "full
    readable review" side of the distinction (the `ActionProposal` object
    itself, already returned in full by `GET /approvals/{id}`) is for. A
    person must still see the full review before approving anything —
    this is only ever a spoken preview, never a substitute for it."""
    return (
        f"{proposal.summary}. This is a {proposal.risk_level.value}-risk action "
        f"affecting {proposal.target_system}."
    )
