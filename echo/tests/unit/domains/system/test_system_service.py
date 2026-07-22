from datetime import UTC, datetime, timedelta

import pytest

from core.time import FakeClock
from domains.system.errors import (
    AlertNotFoundError,
    HallucinationIncidentAlreadyResolvedError,
    HallucinationIncidentNotFoundError,
    InvalidAlertTransitionError,
    MonitorNotFoundError,
)
from domains.system.models import AlertStatus, HallucinationIncidentStatus, MonitorType
from domains.system.service import SystemService
from tests.unit.domains.system.fakes import FakeAuditRepository, FakeSystemRepository


def _service(clock: FakeClock | None = None) -> tuple[SystemService, FakeSystemRepository]:
    repo = FakeSystemRepository()
    service = SystemService(
        repo, FakeAuditRepository(), clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    )
    return service, repo


async def test_create_monitor_defaults_to_enabled() -> None:
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    assert monitor.enabled is True


async def test_get_monitor_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(MonitorNotFoundError):
        await service.get_monitor("does-not-exist")


async def test_list_monitors_for_user_scopes_correctly() -> None:
    service, _ = _service()
    await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    await service.create_monitor("user_2", MonitorType.STALE_SCHWAB_SYNC)
    monitors = await service.list_monitors_for_user("user_1")
    assert len(monitors) == 1
    assert monitors[0].monitor_type == MonitorType.CALENDAR_CONFLICT


async def test_set_monitor_enabled_disables_a_monitor() -> None:
    """PROMPT.md Phase 24 verification 4: "users can disable a monitor.\" """
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    updated = await service.set_monitor_enabled(monitor.monitor_id, False)
    assert updated.enabled is False

    enabled = await service.list_all_enabled_monitors()
    assert monitor.monitor_id not in [m.monitor_id for m in enabled]


async def test_raise_alert_creates_a_real_alert() -> None:
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    alert = await service.raise_alert(
        monitor,
        message="Two events overlap",
        reason="event_a and event_b overlap",
        severity="medium",
        dedup_key="calendar_conflict:event_a:event_b",
        created_during_quiet_hours=False,
    )
    assert alert is not None
    assert alert.status == AlertStatus.ACTIVE
    assert alert.reason == "event_a and event_b overlap"


async def test_raise_alert_deduplicates_by_key() -> None:
    """PROMPT.md Phase 24 verification 2: "duplicate alerts are
    suppressed.\" """
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    first = await service.raise_alert(
        monitor,
        message="Two events overlap",
        reason="event_a and event_b overlap",
        severity="medium",
        dedup_key="dedup-key-1",
        created_during_quiet_hours=False,
    )
    second = await service.raise_alert(
        monitor,
        message="Two events overlap (again)",
        reason="event_a and event_b overlap, again",
        severity="medium",
        dedup_key="dedup-key-1",
        created_during_quiet_hours=False,
    )
    assert first is not None
    assert second is None


async def test_raise_alert_allows_a_new_one_after_the_old_is_acknowledged() -> None:
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    first = await service.raise_alert(
        monitor,
        message="m",
        reason="r",
        severity="low",
        dedup_key="dedup-key-1",
        created_during_quiet_hours=False,
    )
    assert first is not None
    await service.acknowledge_alert(first.alert_id)

    second = await service.raise_alert(
        monitor,
        message="m",
        reason="r",
        severity="low",
        dedup_key="dedup-key-1",
        created_during_quiet_hours=False,
    )
    assert second is not None


async def test_acknowledge_alert() -> None:
    """PROMPT.md Phase 24 implement item 8: "alert acknowledgement.\" """
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    alert = await service.raise_alert(
        monitor,
        message="m",
        reason="r",
        severity="low",
        dedup_key="k",
        created_during_quiet_hours=False,
    )
    assert alert is not None
    acknowledged = await service.acknowledge_alert(alert.alert_id)
    assert acknowledged.status == AlertStatus.ACKNOWLEDGED
    assert acknowledged.acknowledged_at is not None


async def test_suppress_alert() -> None:
    """PROMPT.md Phase 24 implement item 9: "alert suppression.\" """
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    alert = await service.raise_alert(
        monitor,
        message="m",
        reason="r",
        severity="low",
        dedup_key="k",
        created_during_quiet_hours=False,
    )
    assert alert is not None
    suppressed = await service.suppress_alert(alert.alert_id)
    assert suppressed.status == AlertStatus.SUPPRESSED


async def test_acknowledge_alert_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(AlertNotFoundError):
        await service.acknowledge_alert("does-not-exist")


async def test_cannot_acknowledge_an_already_terminal_alert() -> None:
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.CALENDAR_CONFLICT)
    alert = await service.raise_alert(
        monitor,
        message="m",
        reason="r",
        severity="low",
        dedup_key="k",
        created_during_quiet_hours=False,
    )
    assert alert is not None
    await service.suppress_alert(alert.alert_id)

    with pytest.raises(InvalidAlertTransitionError):
        await service.acknowledge_alert(alert.alert_id)


async def test_record_evaluation_run_is_append_only() -> None:
    """PROMPT.md Phase 24 implement item 10: "evaluation audit.\" """
    service, _ = _service()
    monitor = await service.create_monitor("user_1", MonitorType.STALE_SCHWAB_SYNC)
    await service.record_evaluation_run(monitor, triggered=False, detail="fresh")
    await service.record_evaluation_run(monitor, triggered=True, detail="stale")

    runs = await service.list_evaluation_runs_for_monitor(monitor.monitor_id)
    assert len(runs) == 2
    assert [r.triggered for r in runs] == [False, True]


async def test_report_hallucination_creates_an_open_incident() -> None:
    service, _ = _service()
    incident = await service.report_hallucination("user_1", description="claimed X falsely")
    assert incident.status == HallucinationIncidentStatus.OPEN
    assert incident.resolved_at is None


async def test_resolve_hallucination_seeds_a_regression_case() -> None:
    """PROMPT.md Phase 25: "Create regression datasets from corrected
    failures.\" """
    service, _ = _service()
    incident = await service.report_hallucination("user_1", description="claimed X falsely")
    resolved = await service.resolve_hallucination(
        incident.incident_id, resolution_note="the correct answer is Y"
    )
    assert resolved.status == HallucinationIncidentStatus.RESOLVED
    assert resolved.resolution_note == "the correct answer is Y"
    assert resolved.resolved_at is not None

    cases = await service.list_regression_cases()
    assert len(cases) == 1
    assert cases[0].source_type == "hallucination_incident"
    assert cases[0].source_id == incident.incident_id
    assert cases[0].incorrect_output == "claimed X falsely"
    assert cases[0].corrected_output == "the correct answer is Y"


async def test_resolve_hallucination_raises_when_missing() -> None:
    service, _ = _service()
    with pytest.raises(HallucinationIncidentNotFoundError):
        await service.resolve_hallucination("does-not-exist", resolution_note="n/a")


async def test_cannot_resolve_an_already_resolved_incident() -> None:
    service, _ = _service()
    incident = await service.report_hallucination("user_1", description="claimed X falsely")
    await service.resolve_hallucination(incident.incident_id, resolution_note="Y")

    with pytest.raises(HallucinationIncidentAlreadyResolvedError):
        await service.resolve_hallucination(incident.incident_id, resolution_note="Y again")


async def test_list_hallucination_incidents_for_user_scopes_correctly() -> None:
    service, _ = _service()
    await service.report_hallucination("user_1", description="a")
    await service.report_hallucination("user_2", description="b")
    incidents = await service.list_hallucination_incidents_for_user("user_1")
    assert len(incidents) == 1
    assert incidents[0].description == "a"


async def test_list_hallucination_incidents_since_excludes_older_reports() -> None:
    clock = FakeClock(datetime(2026, 1, 10, tzinfo=UTC))
    service, _ = _service(clock)
    await service.report_hallucination("user_1", description="recent")
    since = clock.now_utc() - timedelta(days=1)
    incidents = await service.list_hallucination_incidents_since(since)
    assert len(incidents) == 1


async def test_record_regression_case_directly_for_user_corrections() -> None:
    """The second path into the regression dataset — a user-initiated
    memory correction (application/orchestrators/trust.py), not a
    resolved hallucination incident."""
    service, _ = _service()
    case = await service.record_regression_case(
        source_type="user_correction",
        source_id="memory_1",
        incorrect_output="old fact",
        corrected_output="new fact",
    )
    assert case.source_type == "user_correction"
    cases = await service.list_regression_cases()
    assert cases == [case]
