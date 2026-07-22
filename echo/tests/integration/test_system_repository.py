from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.system.models import AlertSeverity, AlertStatus, MonitorType
from domains.system.repository import PostgresSystemRepository
from domains.system.schemas import Alert, EvaluationRun, MonitorDefinition


async def test_monitor_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresSystemRepository(db_session)
    monitor = MonitorDefinition(
        user_id="user_1",
        monitor_type=MonitorType.CALENDAR_CONFLICT,
        quiet_hours_start_utc=22,
        quiet_hours_end_utc=7,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_monitor(monitor)

    restored = await repo.get_monitor(monitor.monitor_id)
    assert restored is not None
    assert restored.monitor_type == MonitorType.CALENDAR_CONFLICT
    assert restored.quiet_hours_start_utc == 22
    assert restored.quiet_hours_end_utc == 7


async def test_monitor_save_upserts_by_monitor_id(db_session: AsyncSession) -> None:
    repo = PostgresSystemRepository(db_session)
    monitor = MonitorDefinition(
        user_id="system_repo_test_user",
        monitor_type=MonitorType.STALE_SCHWAB_SYNC,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_monitor(monitor)

    disabled = monitor.model_copy(
        update={"enabled": False, "updated_at": datetime(2026, 1, 2, tzinfo=UTC)}
    )
    await repo.save_monitor(disabled)

    restored = await repo.get_monitor(monitor.monitor_id)
    assert restored is not None
    assert restored.enabled is False


async def test_list_monitors_for_user_scopes_correctly(db_session: AsyncSession) -> None:
    repo = PostgresSystemRepository(db_session)
    mine = MonitorDefinition(
        user_id="system_repo_test_user_a",
        monitor_type=MonitorType.CALENDAR_CONFLICT,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    other = MonitorDefinition(
        user_id="system_repo_test_user_b",
        monitor_type=MonitorType.CALENDAR_CONFLICT,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_monitor(mine)
    await repo.save_monitor(other)

    matches = await repo.list_monitors_for_user("system_repo_test_user_a")
    assert [m.monitor_id for m in matches] == [mine.monitor_id]


async def test_list_all_enabled_monitors_excludes_disabled(db_session: AsyncSession) -> None:
    repo = PostgresSystemRepository(db_session)
    enabled = MonitorDefinition(
        user_id="system_repo_test_user_c",
        monitor_type=MonitorType.IPS_CONCENTRATION_BREACH,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_monitor(enabled)
    disabled = MonitorDefinition(
        user_id="system_repo_test_user_c",
        monitor_type=MonitorType.MATERIAL_PORTFOLIO_NEWS,
        enabled=False,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_monitor(disabled)

    enabled_ids = {m.monitor_id for m in await repo.list_all_enabled_monitors()}
    assert enabled.monitor_id in enabled_ids
    assert disabled.monitor_id not in enabled_ids


async def test_alert_save_get_and_list(db_session: AsyncSession) -> None:
    repo = PostgresSystemRepository(db_session)
    alert = Alert(
        monitor_id="monitor_1",
        user_id="system_repo_test_user_d",
        monitor_type=MonitorType.CALENDAR_CONFLICT,
        severity=AlertSeverity.MEDIUM,
        message="Two calendar events overlap",
        reason='"Meeting A" and "Meeting B" have overlapping time ranges in the next 2 days',
        dedup_key="system_repo_test_dedup_1",
        triggered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_alert(alert)

    fetched = await repo.get_alert(alert.alert_id)
    assert fetched is not None
    assert fetched.status == AlertStatus.ACTIVE
    assert fetched.reason == alert.reason

    listed = await repo.list_alerts_for_user("system_repo_test_user_d")
    assert len(listed) == 1


async def test_get_active_alert_by_dedup_key_ignores_terminal_alerts(
    db_session: AsyncSession,
) -> None:
    repo = PostgresSystemRepository(db_session)
    alert = Alert(
        monitor_id="monitor_1",
        user_id="system_repo_test_user_e",
        monitor_type=MonitorType.CALENDAR_CONFLICT,
        severity=AlertSeverity.LOW,
        message="m",
        reason="r",
        dedup_key="system_repo_test_dedup_2",
        triggered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_alert(alert)

    active = await repo.get_active_alert_by_dedup_key("system_repo_test_dedup_2")
    assert active is not None

    acknowledged = alert.model_copy(
        update={
            "status": AlertStatus.ACKNOWLEDGED,
            "acknowledged_at": datetime(2026, 1, 2, tzinfo=UTC),
        }
    )
    await repo.save_alert(acknowledged)

    assert await repo.get_active_alert_by_dedup_key("system_repo_test_dedup_2") is None


async def test_evaluation_run_save_is_append_only_and_lists(db_session: AsyncSession) -> None:
    """PROMPT.md Phase 24 implement item 10: "evaluation audit" — proven
    against real Postgres, not just the in-memory fake."""
    repo = PostgresSystemRepository(db_session)
    first = EvaluationRun(
        monitor_id="system_repo_test_monitor_1",
        user_id="system_repo_test_user_f",
        monitor_type=MonitorType.STALE_SCHWAB_SYNC,
        evaluated_at=datetime(2026, 1, 1, tzinfo=UTC),
        triggered=False,
        detail="fresh",
    )
    second = EvaluationRun(
        monitor_id="system_repo_test_monitor_1",
        user_id="system_repo_test_user_f",
        monitor_type=MonitorType.STALE_SCHWAB_SYNC,
        evaluated_at=datetime(2026, 1, 2, tzinfo=UTC),
        triggered=True,
        detail="stale",
    )
    await repo.save_evaluation_run(first)
    await repo.save_evaluation_run(second)

    listed = await repo.list_evaluation_runs_for_monitor("system_repo_test_monitor_1")
    assert {r.evaluation_id for r in listed} == {first.evaluation_id, second.evaluation_id}
