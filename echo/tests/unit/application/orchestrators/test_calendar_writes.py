"""Uses real ApprovalService + real CalendarService, both backed by fakes
(matching tests/unit/domains/approvals/test_approval_service.py's own
pattern) — this proves the orchestrator's wiring against the actual Phase 6
state machine, not a re-implementation of it.
"""

from datetime import UTC, datetime, timedelta

import pytest

from application.orchestrators.calendar_writes import CalendarWriteOrchestrator
from core.errors import ApprovalRequiredError, ValidationError
from core.time import FakeClock
from domains.approvals.models import ProposalStatus
from domains.approvals.service import ApprovalService
from domains.calendar.models import RecurringEditScope
from domains.calendar.service import CalendarService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.approvals.fakes import (
    FakeApprovalDecisionRepository,
    FakeApprovalProposalRepository,
)
from tests.unit.domains.calendar.fakes import (
    FakeAuditRepository,
    FakeCalendarCredentialRepository,
    FakeCalendarEventRepository,
    FakeCalendarProvider,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _orchestrator(
    clock: FakeClock | None = None, provider: FakeCalendarProvider | None = None
) -> tuple[
    CalendarWriteOrchestrator,
    ApprovalService,
    CalendarService,
    FakeCalendarProvider,
    FakeCalendarEventRepository,
]:
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = provider or FakeCalendarProvider()
    events_repo = FakeCalendarEventRepository()
    approvals = ApprovalService(
        FakeApprovalProposalRepository(),
        FakeApprovalDecisionRepository(),
        FakeAuditRepository(),
        clock,
    )
    calendar = CalendarService(
        FakeCalendarCredentialRepository(),
        events_repo,
        provider,
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        clock,
        "state-secret",
    )
    orchestrator = CalendarWriteOrchestrator(approvals, calendar, provider)
    return orchestrator, approvals, calendar, provider, events_repo


async def _connected(calendar: CalendarService, user_id: str = "user_1") -> None:
    await calendar.connect(user_id, "auth-code")


async def test_propose_create_event_builds_google_shaped_payload_and_awaits_approval() -> None:
    orchestrator, _, calendar, _, _ = _orchestrator()
    await _connected(calendar)

    proposal = await orchestrator.propose_create_event(
        "user_1",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
        timezone="America/Los_Angeles",
    )

    assert proposal.status == ProposalStatus.AWAITING_APPROVAL
    assert proposal.payload["action"] == "create_event"
    assert proposal.payload["start"] == {
        "dateTime": "2026-01-02T09:00:00+00:00",
        "timeZone": "America/Los_Angeles",
    }


async def test_full_lifecycle_no_changes_before_approval() -> None:
    """PROMPT.md Phase 11 verification 1: "No event changes before
    approval." """
    orchestrator, _, _, provider, _ = _orchestrator()

    await orchestrator.propose_create_event(
        "user_1",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
    )

    assert not any(c[0] == "create_event" for c in provider.calls)


async def test_execute_before_approval_is_rejected() -> None:
    orchestrator, _, calendar, _, _ = _orchestrator()
    await _connected(calendar)

    proposal = await orchestrator.propose_create_event(
        "user_1",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
    )

    with pytest.raises(ApprovalRequiredError):
        await orchestrator.execute_proposal(proposal.proposal_id, "user_1")


async def test_full_proposal_payload_appears_in_review() -> None:
    """PROMPT.md Phase 11 verification 2."""
    orchestrator, approvals, _, _, _ = _orchestrator()

    proposal = await orchestrator.propose_create_event(
        "user_1",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
        description="Daily sync",
    )

    reviewed = await approvals.get_proposal(proposal.proposal_id)
    assert reviewed.payload["summary"] == "Standup"
    assert reviewed.payload["description"] == "Daily sync"
    assert reviewed.payload["calendar_id"] == "primary"


async def test_approved_create_event_executes_and_caches_result() -> None:
    orchestrator, approvals, calendar, provider, _ = _orchestrator()
    await _connected(calendar)
    provider.create_event_response = {
        "id": "google-new-id",
        "summary": "Standup",
        "start": {"dateTime": "2026-01-02T09:00:00Z"},
        "end": {"dateTime": "2026-01-02T09:15:00Z"},
    }
    provider.get_event_response = provider.create_event_response

    proposal = await orchestrator.propose_create_event(
        "user_1",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    executed = await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert executed.status == ProposalStatus.EXECUTED
    cached = await calendar.get_event("user_1", event_id="google-new-id")
    assert cached.summary == "Standup"


async def test_duplicate_execution_of_same_proposal_does_not_create_a_second_event() -> None:
    """PROMPT.md Phase 11 verification 3: "Duplicate event creation is
    prevented" — proves the Approval Engine's own idempotent-execute
    guarantee (Phase 6) holds for a real Calendar write, not just in the
    abstract."""
    orchestrator, approvals, calendar, provider, _ = _orchestrator()
    await _connected(calendar)
    provider.create_event_response = {
        "id": "google-new-id",
        "summary": "Standup",
        "start": {"dateTime": "2026-01-02T09:00:00Z"},
        "end": {"dateTime": "2026-01-02T09:15:00Z"},
    }
    provider.get_event_response = provider.create_event_response

    proposal = await orchestrator.propose_create_event(
        "user_1",
        summary="Standup",
        start=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        end=datetime(2026, 1, 2, 9, 15, tzinfo=UTC),
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))

    await orchestrator.execute_proposal(proposal.proposal_id, "user_1")
    await orchestrator.execute_proposal(
        proposal.proposal_id, "user_1"
    )  # re-execute the same proposal

    assert len([c for c in provider.calls if c[0] == "create_event"]) == 1


async def test_delete_execution_evicts_event_from_cache() -> None:
    orchestrator, approvals, calendar, provider, events_repo = _orchestrator()
    await _connected(calendar)
    provider.events_response = [
        {
            "id": "to-delete",
            "summary": "Old meeting",
            "start": {"dateTime": "2026-01-02T09:00:00Z"},
            "end": {"dateTime": "2026-01-02T09:15:00Z"},
        }
    ]
    await calendar.list_events(
        "user_1",
        time_min=datetime(2026, 1, 2, tzinfo=UTC),
        time_max=datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert await events_repo.get("user_1", "to-delete") is not None

    proposal = await orchestrator.propose_delete_event(
        "user_1",
        provider_event_id="to-delete",
        recurring_event_id=None,
        scope=RecurringEditScope.SINGLE_INSTANCE,
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    provider.get_event_response = {"id": "to-delete", "status": "cancelled"}
    executed = await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    assert executed.status == ProposalStatus.EXECUTED
    assert await events_repo.get("user_1", "to-delete") is None


async def test_modify_scope_entire_series_requires_recurring_event_id() -> None:
    """PROMPT.md Phase 11 verification 5: "Recurring event scope is
    explicit" — an entire_series edit with no series to point at is
    rejected rather than silently falling back to single-instance."""
    orchestrator, _, _, _, _ = _orchestrator()

    with pytest.raises(ValidationError):
        await orchestrator.propose_modify_event(
            "user_1",
            provider_event_id="inst-1",
            recurring_event_id=None,
            scope=RecurringEditScope.ENTIRE_SERIES,
            summary="Renamed",
        )


async def test_delete_scope_entire_series_requires_recurring_event_id() -> None:
    orchestrator, _, _, _, _ = _orchestrator()

    with pytest.raises(ValidationError):
        await orchestrator.propose_delete_event(
            "user_1",
            provider_event_id="inst-1",
            recurring_event_id=None,
            scope=RecurringEditScope.ENTIRE_SERIES,
        )


async def test_modify_scope_entire_series_targets_recurring_parent() -> None:
    orchestrator, approvals, calendar, provider, _ = _orchestrator()
    await _connected(calendar)
    provider.update_event_response = {
        "id": "series-1",
        "summary": "All renamed",
        "start": {"dateTime": "2026-01-02T09:00:00Z"},
        "end": {"dateTime": "2026-01-02T09:15:00Z"},
    }
    provider.get_event_response = provider.update_event_response

    proposal = await orchestrator.propose_modify_event(
        "user_1",
        provider_event_id="inst-1",
        recurring_event_id="series-1",
        scope=RecurringEditScope.ENTIRE_SERIES,
        summary="All renamed",
    )
    await approvals.approve(proposal.proposal_id, "approving_user", approval_ttl=timedelta(hours=1))
    await orchestrator.execute_proposal(proposal.proposal_id, "user_1")

    update_call = next(c for c in provider.calls if c[0] == "update_event")
    assert update_call[1]["event_id"] == "series-1"
