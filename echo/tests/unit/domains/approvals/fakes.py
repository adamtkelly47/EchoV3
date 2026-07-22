"""In-memory fakes for fast approval-engine unit tests, plus the fake
external write adapter PROMPT.md Phase 6 explicitly calls for.
"""

from __future__ import annotations

from typing import Any

from domains.approvals.models import ProposalStatus
from domains.approvals.schemas import ActionProposal, ApprovalDecision


class FakeApprovalProposalRepository:
    def __init__(self) -> None:
        self._store: dict[str, ActionProposal] = {}

    async def save(self, proposal: ActionProposal) -> None:
        self._store[proposal.proposal_id] = proposal

    async def get(self, proposal_id: str) -> ActionProposal | None:
        return self._store.get(proposal_id)

    async def list_pending_for_user(self, user_id: str) -> list[ActionProposal]:
        return [
            p
            for p in self._store.values()
            if p.user_id == user_id and p.status == ProposalStatus.AWAITING_APPROVAL
        ]


class FakeApprovalDecisionRepository:
    def __init__(self) -> None:
        self._by_proposal: dict[str, list[ApprovalDecision]] = {}

    async def save(self, decision: ApprovalDecision) -> None:
        self._by_proposal.setdefault(decision.proposal_id, []).append(decision)

    async def get_latest_for_proposal(self, proposal_id: str) -> ApprovalDecision | None:
        decisions = self._by_proposal.get(proposal_id)
        return decisions[-1] if decisions else None


class FakeAuditRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        call_id = f"audit_fake_{len(self.recorded)}"
        self.recorded.append(
            {
                "audit_id": call_id,
                "action": action,
                "result": result,
                "correlation_id": correlation_id,
                "capability_id": capability_id,
                "approval_id": approval_id,
                "detail": detail,
            }
        )
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e["correlation_id"] == correlation_id]


class FakeWriteAdapter:
    """PROMPT.md Phase 6: "Use a fake external write adapter." Configurable
    to succeed or raise, so execution-failure handling can be tested."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, Any]] = []

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.should_fail:
            raise RuntimeError("fake external system rejected the write")
        return {"external_id": "fake-external-123", "status": "created"}


class FakeVerifier:
    def __init__(self, *, verified: bool = True) -> None:
        self.verified = verified
        self.calls: list[dict[str, Any]] = []

    async def verify(self, execution_result: dict[str, Any]) -> bool:
        self.calls.append(execution_result)
        return self.verified
