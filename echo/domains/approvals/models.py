"""The approval state machine (Docs/APPROVAL_MODEL.md). Invalid transitions
are rejected in code, not merely discouraged by convention
(CONSTITUTION.md: Approval Principle).
"""

from __future__ import annotations

from enum import Enum


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTING = "executing"
    EXECUTED = "executed"
    VERIFICATION_FAILED = "verification_failed"
    EXECUTION_FAILED = "execution_failed"
    CANCELLED = "cancelled"


VALID_TRANSITIONS: dict[ProposalStatus, frozenset[ProposalStatus]] = {
    ProposalStatus.DRAFT: frozenset({ProposalStatus.VALIDATED, ProposalStatus.CANCELLED}),
    ProposalStatus.VALIDATED: frozenset(
        {ProposalStatus.AWAITING_APPROVAL, ProposalStatus.CANCELLED}
    ),
    ProposalStatus.AWAITING_APPROVAL: frozenset(
        {
            ProposalStatus.APPROVED,
            ProposalStatus.REJECTED,
            ProposalStatus.EXPIRED,
            ProposalStatus.CANCELLED,
        }
    ),
    ProposalStatus.APPROVED: frozenset(
        {ProposalStatus.EXECUTING, ProposalStatus.EXPIRED, ProposalStatus.CANCELLED}
    ),
    ProposalStatus.EXECUTING: frozenset({ProposalStatus.EXECUTED, ProposalStatus.EXECUTION_FAILED}),
    ProposalStatus.EXECUTED: frozenset({ProposalStatus.VERIFICATION_FAILED}),
    ProposalStatus.REJECTED: frozenset(),
    ProposalStatus.EXPIRED: frozenset(),
    ProposalStatus.EXECUTION_FAILED: frozenset(),
    ProposalStatus.VERIFICATION_FAILED: frozenset(),
    ProposalStatus.CANCELLED: frozenset(),
}

# The proposal creator is always the system, acting on a user's request — a
# human never creates a proposal directly, and the system can never be the
# *approver* of its own proposal (CONSTITUTION.md: "Echo shall never approve
# its own proposals."). See domains.approvals.service for the enforcement.
SYSTEM_ACTOR = "system"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
