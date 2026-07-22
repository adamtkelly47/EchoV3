"""Domain-agnostic Approval Engine review/approve/reject surface (Docs/
APPROVAL_MODEL.md) — shared platform logic, not specific to Calendar.
Execution stays domain-specific (apps/api/routes/calendar.py's own
`/calendar/proposals/{id}/execute`) since only the domain that proposed a
write knows which concrete WriteAdapter/ExecutionVerifier to run it with.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_approval_service, get_db_session
from apps.api.schemas.approvals import (
    ApprovalDecisionResponse,
    ApproveRequest,
    ProposalResponse,
    SpokenSummaryResponse,
)
from domains.approvals.models import ConfirmationMethod
from domains.approvals.policies import build_spoken_summary
from domains.approvals.schemas import ActionProposal, ApprovalDecision
from domains.approvals.service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["approvals"])

_APPROVAL_TTL = timedelta(hours=1)


def _to_response(proposal: ActionProposal) -> ProposalResponse:
    return ProposalResponse(
        proposal_id=proposal.proposal_id,
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        summary=proposal.summary,
        payload=proposal.payload,
        target_system=proposal.target_system,
        expected_effect=proposal.expected_effect,
        risk_level=proposal.risk_level.value,
        status=proposal.status.value,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        warnings=proposal.warnings,
    )


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str, approvals: ApprovalService = Depends(get_approval_service)
) -> ProposalResponse:
    """The "full readable review" side of PROMPT.md Phase 26 implement
    item 6 — every field a person must actually see before approving,
    never summarized. See `GET /{proposal_id}/spoken-summary` for the
    short, TTS-appropriate counterpart."""
    proposal = await approvals.get_proposal(proposal_id)
    return _to_response(proposal)


@router.get("/{proposal_id}/spoken-summary", response_model=SpokenSummaryResponse)
async def get_spoken_summary(
    proposal_id: str, approvals: ApprovalService = Depends(get_approval_service)
) -> SpokenSummaryResponse:
    """PROMPT.md Phase 26 implement item 6: the spoken-summary side of the
    distinction — short and TTS-appropriate, never a substitute for the
    full review `GET /{proposal_id}` returns."""
    proposal = await approvals.get_proposal(proposal_id)
    return SpokenSummaryResponse(
        proposal_id=proposal.proposal_id, spoken_summary=build_spoken_summary(proposal)
    )


@router.post("/{proposal_id}/approve", response_model=ApprovalDecisionResponse)
async def approve(
    proposal_id: str,
    body: ApproveRequest,
    approvals: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalDecisionResponse:
    decision: ApprovalDecision = await approvals.approve(
        proposal_id,
        body.approving_user_id,
        approval_ttl=_APPROVAL_TTL,
        confirmation_method=ConfirmationMethod(body.confirmation_method),
    )
    await session.commit()
    return ApprovalDecisionResponse(
        approval_id=decision.approval_id,
        proposal_id=decision.proposal_id,
        approving_user_id=decision.approving_user_id,
        approved_at=decision.approved_at,
        approval_expires_at=decision.approval_expires_at,
        confirmation_method=decision.confirmation_method.value,
    )


@router.post("/{proposal_id}/reject", response_model=ProposalResponse)
async def reject(
    proposal_id: str,
    approvals: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await approvals.reject(proposal_id)
    await session.commit()
    return _to_response(proposal)
