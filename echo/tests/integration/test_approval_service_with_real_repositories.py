"""Proves the approval engine composes correctly with the real
Postgres-backed proposal/decision repositories, not just the in-memory
fakes used for the fast unit tests in tests/unit/domains/approvals/.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import FakeClock
from domains.approvals.errors import VoiceConfirmationNotAllowedForHighRiskError
from domains.approvals.models import ConfirmationMethod, ProposalStatus, RiskLevel
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


async def test_list_pending_for_user_against_real_postgres(db_session: AsyncSession) -> None:
    """PROMPT.md Phase 22 implement item 7: "approval inbox.\" """
    service = ApprovalService(
        proposals=PostgresApprovalProposalRepository(db_session),
        decisions=PostgresApprovalDecisionRepository(db_session),
        audit=PostgresAuditRepository(db_session),
        clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )

    async def _propose_and_submit(user_id: str) -> str:
        proposal = await service.propose(
            user_id=user_id,
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
        return proposal.proposal_id

    pending = await _propose_and_submit("dashboard_test_user")
    rejected = await _propose_and_submit("dashboard_test_user")
    await service.reject(rejected)
    await _propose_and_submit("other_dashboard_test_user")

    inbox = await service.list_pending_for_user("dashboard_test_user")

    assert [p.proposal_id for p in inbox] == [pending]


async def test_confirmation_method_round_trips_against_real_postgres(
    db_session: AsyncSession,
) -> None:
    """PROMPT.md Phase 26 implement item 5: "voice safe approval
    requirement" — proven against real Postgres, not just the in-memory
    fake."""
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
    decision = await service.approve(
        proposal.proposal_id,
        "human_approver",
        approval_ttl=timedelta(minutes=30),
        confirmation_method=ConfirmationMethod.VOICE,
    )
    assert decision.confirmation_method == ConfirmationMethod.VOICE

    reloaded = await PostgresApprovalDecisionRepository(db_session).get_latest_for_proposal(
        proposal.proposal_id
    )
    assert reloaded is not None
    assert reloaded.confirmation_method == ConfirmationMethod.VOICE


async def test_high_risk_voice_confirmation_blocked_against_real_postgres(
    db_session: AsyncSession,
) -> None:
    service = ApprovalService(
        proposals=PostgresApprovalProposalRepository(db_session),
        decisions=PostgresApprovalDecisionRepository(db_session),
        audit=PostgresAuditRepository(db_session),
        clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    proposal = await service.propose(
        user_id="user_1",
        action_type="portfolio.rebalance",
        action_schema_version=1,
        summary="Rebalance portfolio",
        payload={"target": "60/40"},
        target_system="schwab",
        expected_effect="trades are placed",
        risk_level=RiskLevel.HIGH,
        required_permission="portfolio.write",
        ttl=timedelta(hours=1),
    )
    await service.submit_for_approval(proposal.proposal_id)

    with pytest.raises(VoiceConfirmationNotAllowedForHighRiskError):
        await service.approve(
            proposal.proposal_id,
            "human_approver",
            approval_ttl=timedelta(minutes=30),
            confirmation_method=ConfirmationMethod.VOICE,
        )
