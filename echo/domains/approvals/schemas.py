"""Typed contracts matching Docs/APPROVAL_MODEL.md's Action Proposal and
Approval Binding field lists exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.approvals.models import ConfirmationMethod, ProposalStatus, RiskLevel


class ActionProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: new_id("proposal"))
    user_id: str
    action_type: str
    action_schema_version: int
    summary: str
    payload: dict[str, Any]
    target_system: str
    expected_effect: str
    risk_level: RiskLevel
    required_permission: str
    created_at: datetime
    expires_at: datetime
    created_by: str
    validation_result: str | None = None
    warnings: list[str] = Field(default_factory=list)
    source_context: str | None = None
    payload_hash: str
    status: ProposalStatus = ProposalStatus.DRAFT


class ApprovalDecision(BaseModel):
    approval_id: str = Field(default_factory=lambda: new_id("approval"))
    proposal_id: str
    payload_hash: str
    approving_user_id: str
    approved_at: datetime
    approval_expires_at: datetime
    confirmation_challenge: str | None = None
    confirmation_method: ConfirmationMethod = ConfirmationMethod.READABLE
