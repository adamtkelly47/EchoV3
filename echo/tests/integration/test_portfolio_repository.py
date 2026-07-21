from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domains.portfolio.models import AssetType
from domains.portfolio.repository import (
    PostgresPortfolioRepository,
    PostgresSchwabCredentialRepository,
)
from domains.portfolio.schemas import (
    Account,
    AccountBalance,
    PortfolioSnapshot,
    Position,
    SchwabCredential,
)


async def test_credential_save_and_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresSchwabCredentialRepository(db_session)
    credential = SchwabCredential(
        user_id="user_1",
        encrypted_access_token="enc-access",
        encrypted_refresh_token="enc-refresh",
        access_token_expires_at=datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC),
        refresh_token_expires_at=datetime(2026, 1, 8, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save(credential)
    restored = await repo.get_for_user("user_1")

    assert restored is not None
    assert restored.encrypted_access_token == "enc-access"
    assert restored.refresh_token_expires_at == datetime(2026, 1, 8, tzinfo=UTC)


async def test_account_save_upserts_by_hash(db_session: AsyncSession) -> None:
    repo = PostgresPortfolioRepository(db_session)
    account = Account(
        user_id="user_1",
        account_hash="hash-1",
        display_mask="••••1234",
        account_type="INDIVIDUAL",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    first_saved = await repo.save_account(account)
    # A second call always arrives with a *fresh* Account (a new random
    # account_id, per domains/portfolio/schemas.py's default_factory) — the
    # same shape domains/portfolio/service.py's real sync() re-parses on
    # every call. The returned value must carry the *original* account_id,
    # not this new throwaway one (a real bug found live — Docs/
    # DECISION_LOG.md's Phase 12 entry: using the wrong one here silently
    # orphaned a fresh set of position/balance rows on every sync).
    fresh_account = Account(
        user_id="user_1",
        account_hash="hash-1",
        display_mask="••••1234",
        account_type="INDIVIDUAL",
        synced_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    second_saved = await repo.save_account(fresh_account)

    assert second_saved.account_id == first_saved.account_id
    accounts = await repo.list_accounts("user_1")
    assert len(accounts) == 1
    assert accounts[0].synced_at == datetime(2026, 1, 2, tzinfo=UTC)


async def test_positions_save_upserts_by_account_and_symbol(db_session: AsyncSession) -> None:
    repo = PostgresPortfolioRepository(db_session)
    position = Position(
        account_id="account_1",
        user_id="user_1",
        symbol="AAPL",
        asset_type=AssetType.EQUITY,
        quantity=100,
        market_value=18500.0,
        source_record_id="source_1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await repo.save_positions([position])
    updated = position.model_copy(
        update={"quantity": 150, "market_value": 27750.0, "asset_type": AssetType.ETF}
    )
    await repo.save_positions([updated])

    positions = await repo.list_positions("user_1", "account_1")
    assert len(positions) == 1
    # Regression: asset_type must actually update on re-sync, not stay
    # frozen at whatever it was classified as the first time (a real bug
    # found live — Docs/DECISION_LOG.md's Phase 12 entry).
    assert positions[0].asset_type == AssetType.ETF
    assert positions[0].quantity == 150


async def test_balance_history_returns_latest(db_session: AsyncSession) -> None:
    repo = PostgresPortfolioRepository(db_session)
    first = AccountBalance(
        account_id="account_1",
        user_id="user_1",
        cash_balance=1000.0,
        schwab_reported_total=1000.0,
        source_record_id="s1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = AccountBalance(
        account_id="account_1",
        user_id="user_1",
        cash_balance=2000.0,
        schwab_reported_total=2000.0,
        source_record_id="s2",
        synced_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await repo.save_balance(first)
    await repo.save_balance(second)

    latest = await repo.get_latest_balance("account_1")
    assert latest is not None
    assert latest.cash_balance == 2000.0


async def test_snapshot_save_and_get_latest(db_session: AsyncSession) -> None:
    repo = PostgresPortfolioRepository(db_session)
    snapshot = PortfolioSnapshot(
        user_id="user_1",
        taken_at=datetime(2026, 1, 1, tzinfo=UTC),
        total_market_value=23500.0,
        reconciled=True,
        reconciliation_diff=0.0,
        account_ids=["account_1"],
        warnings=[],
    )
    await repo.save_snapshot(snapshot)

    latest = await repo.get_latest_snapshot("user_1")
    assert latest is not None
    assert latest.total_market_value == 23500.0
    assert latest.reconciled is True


async def test_raw_response_save(db_session: AsyncSession) -> None:
    repo = PostgresPortfolioRepository(db_session)
    await repo.save_raw_response("raw_1", {"foo": "bar"}, datetime(2026, 1, 1, tzinfo=UTC))
    # No get() on the Protocol — this exercises the insert path itself
    # doesn't raise; the real read path is core.provenance's SourceRecord
    # pointing at raw_storage_ref, tested at the service layer.
