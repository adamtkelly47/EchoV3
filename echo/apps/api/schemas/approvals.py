"""API-boundary request/response schemas — never the domain's own
ActionProposal/ApprovalDecision crossing the wire directly (CONSTITUTION.md:
Typed Contracts), matching apps/api/schemas/conversations.py's convention.
Domain-agnostic: this is the shared Approval Engine surface (Docs/
APPROVAL_MODEL.md), not specific to Calendar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProposalResponse(BaseModel):
    proposal_id: str
    user_id: str
    action_type: str
    summary: str
    # PROMPT.md Phase 11 verification 2: "full event payload appears in
    # review" — the raw payload is returned verbatim, not summarized.
    payload: dict[str, Any]
    target_system: str
    expected_effect: str
    risk_level: str
    status: str
    created_at: datetime
    expires_at: datetime
    warnings: list[str]


class ApproveRequest(BaseModel):
    approving_user_id: str


class ApprovalDecisionResponse(BaseModel):
    approval_id: str
    proposal_id: str
    approving_user_id: str
    approved_at: datetime
    approval_expires_at: datetime
