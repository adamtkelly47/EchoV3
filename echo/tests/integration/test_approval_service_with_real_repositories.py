"""Proves the approval engine composes correctly with the real
Postgres-backed proposal/decision repositories, not just the in-memory
fakes used for the fast unit tests in tests/unit/domains/approvals/.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.time import FakeClock
from domains.approvals.models import ProposalStatus, RiskLevel
from domains.approvals.repository import (
    PostgresApprovalDecisionRepository,
    PostgresApprovalProposalRepository,
)
from domains.approvals.service import ApprovalService
from infrastructure.database.repositories.audit import PostgresAuditRepository
from tests.unit.domains.approvals.fakes import FakeVerifier, FakeWriteAdapter


async def test_full_lifecycle_against_real_postgres(db_session: AsyncSession) -> None:
    service = ApprovalService(
        proposals=PostgresApprovalProposalRepository(db_session),
        decisions=PostgresApprovalDecisionRepository(db_session),
        audit=PostgresAuditRepository(db_session),
        clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )

    proposal = await service.propose(
        user_id="user_1",
        action_type="calendar.create_event",
        action_schema_version=1,
        summary="Create a meeting",
        payload={"title": "Standup"},
        target_system="google_calendar",
        expected_effect="a new calendar event is created",
        risk_level=RiskLevel.LOW,
        required_permission="calendar.write",
        ttl=timedelta(hours=1),
    )
    await service.submit_for_approval(proposal.proposal_id)
    await service.approve(
        proposal.proposal_id, "human_approver", approval_ttl=timedelta(minutes=30)
    )

    result = await service.execute(proposal.proposal_id, FakeWriteAdapter(), FakeVerifier())

    assert result.status == ProposalStatus.EXECUTED

    reloaded = await service.get_proposal(proposal.proposal_id)
    assert reloaded.status == ProposalStatus.EXECUTED
