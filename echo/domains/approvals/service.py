"""The Approval Engine. Owns the entire lifecycle: propose, validate,
approve/reject, execute, verify (CONSTITUTION.md: Approval Principle —
"There shall be no exceptions."). No domain outside this one may implement
its own execution or approval flow (ADR_0003).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Protocol

from core.errors import ApprovalExpiredError, ApprovalRequiredError, ExecutionUncertainError
from core.time import Clock
from domains.approvals.errors import (
    InvalidStateTransitionError,
    NoApprovalOnRecordError,
    PayloadMismatchError,
    ProposalNotFoundError,
    SelfApprovalNotAllowedError,
)
from domains.approvals.models import SYSTEM_ACTOR, ProposalStatus, RiskLevel
from domains.approvals.policies import hash_payload, is_expired, is_valid_transition
from domains.approvals.repository import ApprovalDecisionRepository, ApprovalProposalRepository
from domains.approvals.schemas import ActionProposal, ApprovalDecision
from infrastructure.database.repositories.audit import AuditRepository


class WriteAdapter(Protocol):
    """A fake external write adapter for Phase 6 — real provider adapters
    (Google Calendar, Gmail, ...) implement this same Protocol starting
    with each integration's own phase."""

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class ExecutionVerifier(Protocol):
    # Positional-only + underscore-prefixed: this is a Protocol stub body,
    # never actually executed, and vulture doesn't know Protocol method
    # parameters are structurally required but semantically unused here —
    # the underscore is vulture's documented convention for "intentionally
    # unused", and `/` keeps the name out of the actual calling contract.
    async def verify(self, _execution_result: dict[str, Any], /) -> bool: ...


class ApprovalService:
    def __init__(
        self,
        proposals: ApprovalProposalRepository,
        decisions: ApprovalDecisionRepository,
        audit: AuditRepository,
        clock: Clock,
    ) -> None:
        self._proposals = proposals
        self._decisions = decisions
        self._audit = audit
        self._clock = clock

    async def propose(
        self,
        *,
        user_id: str,
        action_type: str,
        action_schema_version: int,
        summary: str,
        payload: dict[str, Any],
        target_system: str,
        expected_effect: str,
        risk_level: RiskLevel,
        required_permission: str,
        ttl: timedelta,
        warnings: list[str] | None = None,
        source_context: str | None = None,
    ) -> ActionProposal:
        now = self._clock.now_utc()
        proposal = ActionProposal(
            user_id=user_id,
            action_type=action_type,
            action_schema_version=action_schema_version,
            summary=summary,
            payload=payload,
            target_system=target_system,
            expected_effect=expected_effect,
            risk_level=risk_level,
            required_permission=required_permission,
            created_at=now,
            expires_at=now + ttl,
            created_by=SYSTEM_ACTOR,
            payload_hash=hash_payload(payload),
            status=ProposalStatus.VALIDATED,
            validation_result="passed",
            warnings=warnings or [],
            source_context=source_context,
        )
        await self._proposals.save(proposal)
        await self._audit.record(
            action="approval.proposed", result="success", capability_id=action_type
        )
        return proposal

    async def get_proposal(self, proposal_id: str) -> ActionProposal:
        return await self._require_proposal(proposal_id)

    async def submit_for_approval(self, proposal_id: str) -> ActionProposal:
        proposal = await self._require_proposal(proposal_id)
        return await self._transition(proposal, ProposalStatus.AWAITING_APPROVAL)

    async def approve(
        self,
        proposal_id: str,
        approving_user_id: str,
        *,
        approval_ttl: timedelta,
        confirmation_challenge: str | None = None,
    ) -> ApprovalDecision:
        if approving_user_id == SYSTEM_ACTOR:
            raise SelfApprovalNotAllowedError("the system may never approve its own proposal")

        proposal = await self._require_proposal(proposal_id)
        await self._transition(proposal, ProposalStatus.APPROVED)

        now = self._clock.now_utc()
        decision = ApprovalDecision(
            proposal_id=proposal_id,
            payload_hash=proposal.payload_hash,
            approving_user_id=approving_user_id,
            approved_at=now,
            approval_expires_at=now + approval_ttl,
            confirmation_challenge=confirmation_challenge,
        )
        await self._decisions.save(decision)
        await self._audit.record(
            action="approval.approved",
            result="success",
            approval_id=decision.approval_id,
            capability_id=proposal.action_type,
        )
        return decision

    async def reject(self, proposal_id: str) -> ActionProposal:
        proposal = await self._require_proposal(proposal_id)
        rejected = await self._transition(proposal, ProposalStatus.REJECTED)
        await self._audit.record(
            action="approval.rejected", result="success", capability_id=proposal.action_type
        )
        return rejected

    async def cancel(self, proposal_id: str) -> ActionProposal:
        proposal = await self._require_proposal(proposal_id)
        return await self._transition(proposal, ProposalStatus.CANCELLED)

    async def edit(self, proposal_id: str, new_payload: dict[str, Any]) -> ActionProposal:
        """Any material edit invalidates prior approval and requires a new
        approval (CONSTITUTION.md) — implemented by cancelling the old
        proposal and creating a fresh one with a new id and a new hash,
        rather than mutating the original."""
        old = await self._require_proposal(proposal_id)
        if old.status not in (ProposalStatus.DRAFT, ProposalStatus.VALIDATED):
            await self._transition(old, ProposalStatus.CANCELLED)

        return await self.propose(
            user_id=old.user_id,
            action_type=old.action_type,
            action_schema_version=old.action_schema_version,
            summary=old.summary,
            payload=new_payload,
            target_system=old.target_system,
            expected_effect=old.expected_effect,
            risk_level=old.risk_level,
            required_permission=old.required_permission,
            ttl=old.expires_at - old.created_at,
            source_context=old.source_context,
        )

    async def execute(
        self,
        proposal_id: str,
        write_adapter: WriteAdapter,
        verifier: ExecutionVerifier,
    ) -> ActionProposal:
        proposal = await self._require_proposal(proposal_id)

        if proposal.status in (
            ProposalStatus.EXECUTED,
            ProposalStatus.EXECUTION_FAILED,
            ProposalStatus.VERIFICATION_FAILED,
        ):
            return proposal  # idempotent: already executed, never re-run the adapter

        if proposal.status != ProposalStatus.APPROVED:
            raise ApprovalRequiredError(f"{proposal_id} is not approved (status={proposal.status})")

        decision = await self._decisions.get_latest_for_proposal(proposal_id)
        if decision is None:
            raise NoApprovalOnRecordError(f"no approval decision found for {proposal_id}")
        if is_expired(decision.approval_expires_at, self._clock.now_utc()):
            raise ApprovalExpiredError(f"approval for {proposal_id} expired")
        current_hash = hash_payload(proposal.payload)
        if current_hash != decision.payload_hash:
            raise PayloadMismatchError(
                f"{proposal_id}'s payload changed after approval — a new approval is required"
            )

        return await self._run_execution(proposal, write_adapter, verifier)

    async def _run_execution(
        self, proposal: ActionProposal, write_adapter: WriteAdapter, verifier: ExecutionVerifier
    ) -> ActionProposal:
        executing = await self._transition(proposal, ProposalStatus.EXECUTING)
        try:
            result = await write_adapter.execute(executing.payload)
        except Exception as exc:
            failed = await self._transition(executing, ProposalStatus.EXECUTION_FAILED)
            await self._audit.record(
                action="approval.execution_failed",
                result="failure",
                capability_id=proposal.action_type,
                detail={"error": str(exc)},
            )
            return failed

        executed = await self._transition(executing, ProposalStatus.EXECUTED)
        verified = await verifier.verify(result)
        if not verified:
            failed = await self._transition(executed, ProposalStatus.VERIFICATION_FAILED)
            await self._audit.record(
                action="approval.verification_failed",
                result="failure",
                capability_id=proposal.action_type,
            )
            raise ExecutionUncertainError(
                f"{proposal.proposal_id} executed but could not be verified externally"
            )

        await self._audit.record(
            action="approval.executed", result="success", capability_id=proposal.action_type
        )
        return executed

    async def _require_proposal(self, proposal_id: str) -> ActionProposal:
        proposal = await self._proposals.get(proposal_id)
        if proposal is None:
            raise ProposalNotFoundError(f"no proposal found with id {proposal_id!r}")
        return proposal

    async def _transition(self, proposal: ActionProposal, target: ProposalStatus) -> ActionProposal:
        if not is_valid_transition(proposal.status, target):
            raise InvalidStateTransitionError(
                f"{proposal.proposal_id}: cannot move from {proposal.status} to {target}"
            )
        updated = proposal.model_copy(update={"status": target})
        await self._proposals.save(updated)
        return updated
