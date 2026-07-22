from datetime import UTC, datetime, timedelta

import pytest

from core.errors import ApprovalExpiredError, ApprovalRequiredError, ExecutionUncertainError
from core.time import FakeClock
from domains.approvals.errors import (
    InvalidStateTransitionError,
    PayloadMismatchError,
    SelfApprovalNotAllowedError,
    VoiceConfirmationNotAllowedForHighRiskError,
)
from domains.approvals.models import SYSTEM_ACTOR, ConfirmationMethod, ProposalStatus, RiskLevel
from domains.approvals.service import ApprovalService
from tests.unit.domains.approvals.fakes import (
    FakeApprovalDecisionRepository,
    FakeApprovalProposalRepository,
    FakeAuditRepository,
    FakeVerifier,
    FakeWriteAdapter,
)


def _service(clock: FakeClock | None = None) -> ApprovalService:
    return ApprovalService(
        proposals=FakeApprovalProposalRepository(),
        decisions=FakeApprovalDecisionRepository(),
        audit=FakeAuditRepository(),
        clock=clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )


async def _propose(service: ApprovalService, **overrides: object) -> str:
    defaults: dict[str, object] = dict(
        user_id="user_1",
        action_type="calendar.create_event",
        action_schema_version=1,
        summary="Create a meeting",
        payload={"title": "Standup", "start": "2026-01-02T09:00:00Z"},
        target_system="google_calendar",
        expected_effect="a new calendar event is created",
        risk_level=RiskLevel.LOW,
        required_permission="calendar.write",
        ttl=timedelta(hours=1),
    )
    defaults.update(overrides)
    proposal = await service.propose(**defaults)  # type: ignore[arg-type]
    return proposal.proposal_id


async def _propose_and_submit(service: ApprovalService, **overrides: object) -> str:
    proposal_id = await _propose(service, **overrides)
    await service.submit_for_approval(proposal_id)
    return proposal_id


async def test_propose_starts_validated() -> None:
    service = _service()
    proposal_id = await _propose(service)
    proposal = await service.get_proposal(proposal_id)
    assert proposal.status == ProposalStatus.VALIDATED
    assert proposal.payload_hash  # a hash was computed


async def test_full_happy_path_executes_and_verifies() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    write_adapter = FakeWriteAdapter()
    verifier = FakeVerifier(verified=True)
    result = await service.execute(proposal_id, write_adapter, verifier)

    assert result.status == ProposalStatus.EXECUTED
    assert len(write_adapter.calls) == 1
    assert len(verifier.calls) == 1


# --- Phase 6 verification criterion: execution without approval fails ---


async def test_execution_without_approval_fails() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)

    with pytest.raises(ApprovalRequiredError):
        await service.execute(proposal_id, FakeWriteAdapter(), FakeVerifier())


# --- Phase 6 verification criterion: self-approval is impossible ---


async def test_self_approval_is_impossible() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)

    with pytest.raises(SelfApprovalNotAllowedError):
        await service.approve(proposal_id, SYSTEM_ACTOR, approval_ttl=timedelta(minutes=30))


# --- Phase 6 verification criterion: approval binds to the exact payload ---


async def test_approval_binds_to_exact_payload_hash() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    decision = await service.approve(
        proposal_id, "human_approver", approval_ttl=timedelta(minutes=30)
    )
    proposal = await service.get_proposal(proposal_id)
    assert decision.payload_hash == proposal.payload_hash


async def test_changing_payload_after_approval_invalidates_execution() -> None:
    """Simulates a payload change slipping through after approval (e.g. a
    bug bypassing the intended edit() flow) — execute() must still catch
    the mismatch by re-hashing, not just trust the stored approval."""
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    proposal = await service.get_proposal(proposal_id)
    tampered = proposal.model_copy(update={"payload": {"title": "Tampered"}})
    await service._proposals.save(tampered)

    with pytest.raises(PayloadMismatchError):
        await service.execute(proposal_id, FakeWriteAdapter(), FakeVerifier())


# --- Phase 6 verification criterion: editing invalidates approval ---


async def test_editing_creates_a_new_proposal_and_cancels_the_old() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    edited = await service.edit(proposal_id, {"title": "Standup (moved)"})

    assert edited.proposal_id != proposal_id
    old = await service.get_proposal(proposal_id)
    assert old.status == ProposalStatus.CANCELLED
    assert edited.status == ProposalStatus.VALIDATED

    # The new proposal has no approval yet — execution must fail.
    await service.submit_for_approval(edited.proposal_id)
    with pytest.raises(ApprovalRequiredError):
        await service.execute(edited.proposal_id, FakeWriteAdapter(), FakeVerifier())


# --- Phase 6 verification criterion: expired approval fails ---


async def test_expired_approval_fails_execution() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service = _service(clock)
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    clock.advance(timedelta(hours=1))  # past the 30-minute approval TTL

    with pytest.raises(ApprovalExpiredError):
        await service.execute(proposal_id, FakeWriteAdapter(), FakeVerifier())


# --- Phase 6 verification criterion: duplicate execution is prevented ---


async def test_duplicate_execution_does_not_call_the_adapter_twice() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    write_adapter = FakeWriteAdapter()
    verifier = FakeVerifier()
    await service.execute(proposal_id, write_adapter, verifier)
    await service.execute(proposal_id, write_adapter, verifier)  # repeat call

    assert len(write_adapter.calls) == 1, "the adapter must not run twice for the same proposal"


# --- Phase 6 verification criterion: failed verification produces the correct state ---


async def test_failed_verification_sets_verification_failed_state() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    with pytest.raises(ExecutionUncertainError):
        await service.execute(proposal_id, FakeWriteAdapter(), FakeVerifier(verified=False))

    proposal = await service.get_proposal(proposal_id)
    assert proposal.status == ProposalStatus.VERIFICATION_FAILED


async def test_failed_write_adapter_sets_execution_failed_state() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))

    result = await service.execute(proposal_id, FakeWriteAdapter(should_fail=True), FakeVerifier())
    assert result.status == ProposalStatus.EXECUTION_FAILED


# --- General state machine discipline ---


async def test_invalid_transition_is_rejected() -> None:
    service = _service()
    proposal_id = await _propose(service)  # status: validated

    # approve() requires awaiting_approval, not validated — must reject.
    with pytest.raises(InvalidStateTransitionError):
        await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))


async def test_rejected_proposal_cannot_be_approved() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service)
    await service.reject(proposal_id)

    with pytest.raises(InvalidStateTransitionError):
        await service.approve(proposal_id, "human_approver", approval_ttl=timedelta(minutes=30))


async def test_list_pending_for_user_only_returns_awaiting_approval() -> None:
    """PROMPT.md Phase 22 implement item 7: "approval inbox." A
    `VALIDATED`-but-not-yet-submitted proposal, and any terminal-state
    proposal, must not appear in the inbox — only proposals genuinely
    awaiting a human decision."""
    service = _service()
    validated_only = await _propose(service, user_id="user_1")
    pending = await _propose_and_submit(service, user_id="user_1")
    rejected = await _propose_and_submit(service, user_id="user_1")
    await service.reject(rejected)

    inbox = await service.list_pending_for_user("user_1")

    assert [p.proposal_id for p in inbox] == [pending]
    assert validated_only not in [p.proposal_id for p in inbox]


async def test_list_pending_for_user_scopes_by_user() -> None:
    service = _service()
    await _propose_and_submit(service, user_id="user_1")
    other_user_pending = await _propose_and_submit(service, user_id="user_2")

    inbox = await service.list_pending_for_user("user_2")

    assert [p.proposal_id for p in inbox] == [other_user_pending]


# --- PROMPT.md Phase 26 verification: "no consequential action may be
# approved solely through an ambiguous voice command. High risk actions
# require an explicit readable confirmation interface." ---


async def test_high_risk_proposal_cannot_be_approved_by_voice_alone() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service, risk_level=RiskLevel.HIGH)

    with pytest.raises(VoiceConfirmationNotAllowedForHighRiskError):
        await service.approve(
            proposal_id,
            "human_approver",
            approval_ttl=timedelta(minutes=30),
            confirmation_method=ConfirmationMethod.VOICE,
        )

    proposal = await service.get_proposal(proposal_id)
    assert proposal.status == ProposalStatus.AWAITING_APPROVAL  # never transitioned


async def test_high_risk_proposal_can_be_approved_by_readable_confirmation() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service, risk_level=RiskLevel.HIGH)

    decision = await service.approve(
        proposal_id,
        "human_approver",
        approval_ttl=timedelta(minutes=30),
        confirmation_method=ConfirmationMethod.READABLE,
    )
    assert decision.confirmation_method == ConfirmationMethod.READABLE


async def test_low_risk_proposal_can_be_approved_by_voice() -> None:
    service = _service()
    proposal_id = await _propose_and_submit(service, risk_level=RiskLevel.LOW)

    decision = await service.approve(
        proposal_id,
        "human_approver",
        approval_ttl=timedelta(minutes=30),
        confirmation_method=ConfirmationMethod.VOICE,
    )
    assert decision.confirmation_method == ConfirmationMethod.VOICE


async def test_approve_defaults_to_readable_confirmation() -> None:
    """Every pre-Phase-26 caller (and any future one that doesn't think
    about channel at all) gets the safe default, not an accidental
    voice-confirmation bypass."""
    service = _service()
    proposal_id = await _propose_and_submit(service, risk_level=RiskLevel.HIGH)

    decision = await service.approve(
        proposal_id, "human_approver", approval_ttl=timedelta(minutes=30)
    )
    assert decision.confirmation_method == ConfirmationMethod.READABLE
