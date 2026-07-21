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


def hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_valid_transition(current: ProposalStatus, target: ProposalStatus) -> bool:
    return target in VALID_TRANSITIONS[current]


def is_expired(expires_at: datetime, now: datetime) -> bool:
    return now >= expires_at


def payload_matches_approval(current_payload_hash: str, approved_payload_hash: str) -> bool:
    return current_payload_hash == approved_payload_hash
