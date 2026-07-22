"""Approvals owns its own persistence — proposals and decisions are
domain-owned aggregate roots (CONSTITUTION.md: Aggregate Ownership:
"ApprovalProposal owns: immutable payload, payload hash, valid transitions,
expiration, approval binding, state validity."), not cross-cutting platform
tables, so the ORM tables live here rather than under
infrastructure/database/tables/ (which is reserved for tables no domain
owns — see Docs/DECISION_LOG.md's Phase 6 entry).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.approvals.models import ProposalStatus
from domains.approvals.schemas import ActionProposal, ApprovalDecision
from infrastructure.database.base import Base


class ApprovalProposalRow(Base):
    __tablename__ = "approval_proposals"

    proposal_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    action_type: Mapped[str] = mapped_column(String, index=True)
    action_schema_version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    target_system: Mapped[str] = mapped_column(String)
    expected_effect: Mapped[str] = mapped_column(String)
    risk_level: Mapped[str] = mapped_column(String)
    required_permission: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String)
    validation_result: Mapped[str | None] = mapped_column(String)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_context: Mapped[str | None] = mapped_column(String)
    payload_hash: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)


class ApprovalDecisionRow(Base):
    __tablename__ = "approval_decisions"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, index=True)
    payload_hash: Mapped[str] = mapped_column(String)
    approving_user_id: Mapped[str] = mapped_column(String)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approval_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmation_challenge: Mapped[str | None] = mapped_column(String)


def _proposal_to_row(proposal: ActionProposal) -> ApprovalProposalRow:
    return ApprovalProposalRow(
        proposal_id=proposal.proposal_id,
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        action_schema_version=proposal.action_schema_version,
        summary=proposal.summary,
        payload=proposal.payload,
        target_system=proposal.target_system,
        expected_effect=proposal.expected_effect,
        risk_level=proposal.risk_level.value,
        required_permission=proposal.required_permission,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        created_by=proposal.created_by,
        validation_result=proposal.validation_result,
        warnings=proposal.warnings,
        source_context=proposal.source_context,
        payload_hash=proposal.payload_hash,
        status=proposal.status.value,
    )


def _row_to_proposal(row: ApprovalProposalRow) -> ActionProposal:
    return ActionProposal(
        proposal_id=row.proposal_id,
        user_id=row.user_id,
        action_type=row.action_type,
        action_schema_version=row.action_schema_version,
        summary=row.summary,
        payload=row.payload,
        target_system=row.target_system,
        expected_effect=row.expected_effect,
        risk_level=row.risk_level,  # type: ignore[arg-type]
        required_permission=row.required_permission,
        created_at=row.created_at,
        expires_at=row.expires_at,
        created_by=row.created_by,
        validation_result=row.validation_result,
        warnings=list(row.warnings),
        source_context=row.source_context,
        payload_hash=row.payload_hash,
        status=row.status,  # type: ignore[arg-type]
    )


class ApprovalProposalRepository(Protocol):
    async def save(self, proposal: ActionProposal) -> None: ...
    async def get(self, proposal_id: str) -> ActionProposal | None: ...
    async def list_pending_for_user(self, user_id: str) -> list[ActionProposal]: ...


class ApprovalDecisionRepository(Protocol):
    async def save(self, decision: ApprovalDecision) -> None: ...
    async def get_latest_for_proposal(self, proposal_id: str) -> ApprovalDecision | None: ...


class PostgresApprovalProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, proposal: ActionProposal) -> None:
        existing = await self._session.get(ApprovalProposalRow, proposal.proposal_id)
        if existing is None:
            self._session.add(_proposal_to_row(proposal))
        else:
            self._update_row(existing, proposal)
        await self._session.flush()

    def _update_row(self, row: ApprovalProposalRow, proposal: ActionProposal) -> None:
        row.status = proposal.status.value
        row.payload = proposal.payload
        row.payload_hash = proposal.payload_hash
        row.validation_result = proposal.validation_result
        row.warnings = proposal.warnings

    async def get(self, proposal_id: str) -> ActionProposal | None:
        row = await self._session.get(ApprovalProposalRow, proposal_id)
        return _row_to_proposal(row) if row is not None else None

    async def list_pending_for_user(self, user_id: str) -> list[ActionProposal]:
        """PROMPT.md Phase 22 implement item 7: "approval inbox." Pending
        means awaiting a human decision — `AWAITING_APPROVAL` specifically,
        not `VALIDATED` (a proposal `ApprovalService.propose` creates but
        `submit_for_approval` hasn't yet moved forward) or any terminal
        state. Ordered most-recent-first, the natural inbox order."""
        result = await self._session.execute(
            select(ApprovalProposalRow)
            .where(
                ApprovalProposalRow.user_id == user_id,
                ApprovalProposalRow.status == ProposalStatus.AWAITING_APPROVAL.value,
            )
            .order_by(ApprovalProposalRow.created_at.desc())
        )
        return [_row_to_proposal(row) for row in result.scalars().all()]


class PostgresApprovalDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, decision: ApprovalDecision) -> None:
        row = ApprovalDecisionRow(
            approval_id=decision.approval_id,
            proposal_id=decision.proposal_id,
            payload_hash=decision.payload_hash,
            approving_user_id=decision.approving_user_id,
            approved_at=decision.approved_at,
            approval_expires_at=decision.approval_expires_at,
            confirmation_challenge=decision.confirmation_challenge,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_latest_for_proposal(self, proposal_id: str) -> ApprovalDecision | None:
        result = await self._session.execute(
            select(ApprovalDecisionRow)
            .where(ApprovalDecisionRow.proposal_id == proposal_id)
            .order_by(ApprovalDecisionRow.approved_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ApprovalDecision(
            approval_id=row.approval_id,
            proposal_id=row.proposal_id,
            payload_hash=row.payload_hash,
            approving_user_id=row.approving_user_id,
            approved_at=row.approved_at,
            approval_expires_at=row.approval_expires_at,
            confirmation_challenge=row.confirmation_challenge,
        )
