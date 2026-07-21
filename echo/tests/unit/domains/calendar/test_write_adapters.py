import pytest

from domains.calendar.write_adapters import (
    CalendarCreateEventWriteAdapter,
    CalendarDeleteEventWriteAdapter,
    CalendarDeleteVerifier,
    CalendarModifyEventWriteAdapter,
    CalendarWriteVerifier,
    target_event_id,
)
from tests.unit.domains.calendar.fakes import FakeCalendarProvider


def test_target_event_id_single_instance_uses_provider_event_id() -> None:
    payload = {
        "provider_event_id": "inst-1",
        "recurring_event_id": "series-1",
        "scope": "single_instance",
    }
    assert target_event_id(payload) == "inst-1"


def test_target_event_id_entire_series_uses_recurring_event_id() -> None:
    payload = {
        "provider_event_id": "inst-1",
        "recurring_event_id": "series-1",
        "scope": "entire_series",
    }
    assert target_event_id(payload) == "series-1"


def test_target_event_id_entire_series_without_recurring_id_raises() -> None:
    payload = {"provider_event_id": "inst-1", "recurring_event_id": None, "scope": "entire_series"}
    with pytest.raises(ValueError):
        target_event_id(payload)


async def test_create_event_write_adapter_calls_provider_with_event_body() -> None:
    provider = FakeCalendarProvider()
    provider.create_event_response = {"id": "new-id", "summary": "Standup"}
    adapter = CalendarCreateEventWriteAdapter(provider, "access-token")

    result = await adapter.execute(
        {
            "action": "create_event",
            "calendar_id": "primary",
            "summary": "Standup",
            "start": {"dateTime": "2026-01-02T09:00:00Z"},
            "end": {"dateTime": "2026-01-02T09:15:00Z"},
        }
    )

    assert result == {"id": "new-id", "summary": "Standup"}
    call = next(c for c in provider.calls if c[0] == "create_event")
    assert call[1]["body"]["summary"] == "Standup"
    assert "provider_event_id" not in call[1]["body"]  # only whitelisted fields cross into the body


async def test_modify_event_write_adapter_targets_the_instance_by_default() -> None:
    provider = FakeCalendarProvider()
    provider.update_event_response = {"id": "inst-1", "summary": "Renamed"}
    adapter = CalendarModifyEventWriteAdapter(provider, "access-token")

    result = await adapter.execute(
        {
            "action": "modify_event",
            "calendar_id": "primary",
            "provider_event_id": "inst-1",
            "recurring_event_id": "series-1",
            "scope": "single_instance",
            "summary": "Renamed",
        }
    )

    assert result == {"id": "inst-1", "summary": "Renamed"}
    call = next(c for c in provider.calls if c[0] == "update_event")
    assert call[1]["event_id"] == "inst-1"


async def test_modify_event_write_adapter_targets_series_when_scoped() -> None:
    provider = FakeCalendarProvider()
    adapter = CalendarModifyEventWriteAdapter(provider, "access-token")

    await adapter.execute(
        {
            "action": "modify_event",
            "calendar_id": "primary",
            "provider_event_id": "inst-1",
            "recurring_event_id": "series-1",
            "scope": "entire_series",
            "summary": "Renamed",
        }
    )

    call = next(c for c in provider.calls if c[0] == "update_event")
    assert call[1]["event_id"] == "series-1"


async def test_delete_event_write_adapter_calls_provider_and_returns_id() -> None:
    provider = FakeCalendarProvider()
    adapter = CalendarDeleteEventWriteAdapter(provider, "access-token")

    result = await adapter.execute(
        {
            "action": "delete_event",
            "calendar_id": "primary",
            "provider_event_id": "inst-1",
            "recurring_event_id": None,
            "scope": "single_instance",
        }
    )

    assert result == {"id": "inst-1"}
    assert any(c[0] == "delete_event" and c[1]["event_id"] == "inst-1" for c in provider.calls)


async def test_write_verifier_reloads_and_confirms_same_id() -> None:
    provider = FakeCalendarProvider()
    provider.get_event_response = {"id": "new-id", "summary": "Standup"}
    verifier = CalendarWriteVerifier(provider, "access-token", "primary")

    assert await verifier.verify({"id": "new-id"}) is True


async def test_write_verifier_fails_when_reload_returns_different_id() -> None:
    provider = FakeCalendarProvider()
    provider.get_event_response = {"id": "different-id"}
    verifier = CalendarWriteVerifier(provider, "access-token", "primary")

    assert await verifier.verify({"id": "new-id"}) is False


async def test_write_verifier_fails_without_an_id_in_the_result() -> None:
    provider = FakeCalendarProvider()
    verifier = CalendarWriteVerifier(provider, "access-token", "primary")

    assert await verifier.verify({}) is False


async def test_delete_verifier_succeeds_when_reload_shows_cancelled() -> None:
    """Docs/DECISION_LOG.md's Phase 11 entry: Google marks a deleted event
    `status: cancelled` rather than 404ing on the next read — verified
    against Google's own documented behavior before writing this."""
    provider = FakeCalendarProvider()
    provider.get_event_response = {"id": "inst-1", "status": "cancelled"}
    verifier = CalendarDeleteVerifier(provider, "access-token", "primary")

    assert await verifier.verify({"id": "inst-1"}) is True


async def test_delete_verifier_fails_when_reload_still_shows_confirmed() -> None:
    provider = FakeCalendarProvider()
    provider.get_event_response = {"id": "inst-1", "status": "confirmed"}
    verifier = CalendarDeleteVerifier(provider, "access-token", "primary")

    assert await verifier.verify({"id": "inst-1"}) is False
