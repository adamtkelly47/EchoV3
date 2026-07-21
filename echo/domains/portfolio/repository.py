"""Portfolio owns its own persistence — credentials, accounts, positions,
balances, and snapshots are domain-owned aggregates (Docs/DOMAIN_OWNERSHIP.md:
"Portfolio repositories own persistence for: accounts, positions,
transactions, holdings, snapshots..."), so the ORM tables live here rather
than under infrastructure/database/tables/ — matching the Approvals,
Conversation, Memory, and Calendar precedent.

`SchwabRawResponseRow` is the concrete storage the platform-wide
`core.provenance.SourceRecord.raw_storage_ref` points to (PROMPT.md Phase 12
implement item 9: "raw response storage policy") — Portfolio owns *where*
raw payloads live; the generic SourceRecord/SourceRecordRepository
(Phase 4) stays provider-agnostic and unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Boolean, DateTime, Float, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.portfolio.models import AssetType
from domains.portfolio.schemas import (
    Account,
    AccountBalance,
    PortfolioSnapshot,
    Position,
    SchwabCredential,
)
from infrastructure.database.base import Base


class SchwabCredentialRow(Base):
    __tablename__ = "schwab_credentials"

    credential_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    encrypted_access_token: Mapped[str] = mapped_column(String)
    encrypted_refresh_token: Mapped[str] = mapped_column(String)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountRow(Base):
    __tablename__ = "portfolio_accounts"

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    account_hash: Mapped[str] = mapped_column(String, index=True, unique=True)
    display_mask: Mapped[str] = mapped_column(String)
    account_type: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PositionRow(Base):
    __tablename__ = "portfolio_positions"

    position_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String)
    asset_type: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float)
    average_price: Mapped[float | None] = mapped_column(Float)
    market_value: Mapped[float | None] = mapped_column(Float)
    current_price: Mapped[float | None] = mapped_column(Float)
    day_change_dollar: Mapped[float | None] = mapped_column(Float)
    day_change_percent: Mapped[float | None] = mapped_column(Float)
    source_record_id: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountBalanceRow(Base):
    __tablename__ = "portfolio_account_balances"

    balance_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    cash_balance: Mapped[float | None] = mapped_column(Float)
    schwab_reported_total: Mapped[float | None] = mapped_column(Float)
    source_record_id: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioSnapshotRow(Base):
    __tablename__ = "portfolio_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total_market_value: Mapped[float] = mapped_column(Float)
    reconciled: Mapped[bool] = mapped_column(Boolean)
    reconciliation_diff: Mapped[float | None] = mapped_column(Float)
    account_ids: Mapped[list[str]] = mapped_column(JSONB)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)


class SchwabRawResponseRow(Base):
    __tablename__ = "schwab_raw_responses"

    raw_response_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SchwabCredentialRepository(Protocol):
    async def save(self, credential: SchwabCredential) -> None: ...
    async def get_for_user(self, user_id: str) -> SchwabCredential | None: ...


class PortfolioRepository(Protocol):
    async def save_account(self, account: Account) -> Account: ...
    async def list_accounts(self, user_id: str) -> list[Account]: ...
    async def save_positions(self, positions: list[Position]) -> None: ...
    async def list_positions(self, user_id: str, account_id: str) -> list[Position]: ...
    async def save_balance(self, balance: AccountBalance) -> None: ...
    async def get_latest_balance(self, account_id: str) -> AccountBalance | None: ...
    async def save_snapshot(self, snapshot: PortfolioSnapshot) -> None: ...
    async def get_latest_snapshot(self, user_id: str) -> PortfolioSnapshot | None: ...
    async def save_raw_response(
        self, raw_response_id: str, payload: dict[str, Any], now: datetime
    ) -> None: ...


class PostgresSchwabCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, credential: SchwabCredential) -> None:
        existing = await self._get_row(credential.user_id)
        if existing is None:
            self._session.add(
                SchwabCredentialRow(
                    credential_id=credential.credential_id,
                    user_id=credential.user_id,
                    encrypted_access_token=credential.encrypted_access_token,
                    encrypted_refresh_token=credential.encrypted_refresh_token,
                    access_token_expires_at=credential.access_token_expires_at,
                    refresh_token_expires_at=credential.refresh_token_expires_at,
                    created_at=credential.created_at,
                    updated_at=credential.updated_at,
                )
            )
        else:
            existing.encrypted_access_token = credential.encrypted_access_token
            existing.encrypted_refresh_token = credential.encrypted_refresh_token
            existing.access_token_expires_at = credential.access_token_expires_at
            existing.refresh_token_expires_at = credential.refresh_token_expires_at
            existing.updated_at = credential.updated_at
        await self._session.flush()

    async def get_for_user(self, user_id: str) -> SchwabCredential | None:
        row = await self._get_row(user_id)
        if row is None:
            return None
        return SchwabCredential(
            credential_id=row.credential_id,
            user_id=row.user_id,
            encrypted_access_token=row.encrypted_access_token,
            encrypted_refresh_token=row.encrypted_refresh_token,
            access_token_expires_at=row.access_token_expires_at,
            refresh_token_expires_at=row.refresh_token_expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _get_row(self, user_id: str) -> SchwabCredentialRow | None:
        result = await self._session.execute(
            select(SchwabCredentialRow).where(SchwabCredentialRow.user_id == user_id)
        )
        return result.scalar_one_or_none()


class PostgresPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_account(self, account: Account) -> Account:
        """Returns the *persisted* Account — critically, with the stable,
        pre-existing `account_id` when one is found by `account_hash`, not
        the fresh random id `account` arrived with. A caller that used the
        incoming `account.account_id` instead (as domains/portfolio/service.py
        did before this fix — a real bug found live, Docs/DECISION_LOG.md's
        Phase 12 entry) would tie every subsequent position/balance save to
        a new, never-reused id every sync, silently accumulating orphaned
        rows rather than ever updating the same account's data."""
        result = await self._session.execute(
            select(AccountRow).where(AccountRow.account_hash == account.account_hash)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            self._session.add(
                AccountRow(
                    account_id=account.account_id,
                    user_id=account.user_id,
                    account_hash=account.account_hash,
                    display_mask=account.display_mask,
                    account_type=account.account_type,
                    synced_at=account.synced_at,
                )
            )
            await self._session.flush()
            return account
        existing.display_mask = account.display_mask
        existing.account_type = account.account_type
        existing.synced_at = account.synced_at
        await self._session.flush()
        return account.model_copy(update={"account_id": existing.account_id})

    async def list_accounts(self, user_id: str) -> list[Account]:
        result = await self._session.execute(
            select(AccountRow).where(AccountRow.user_id == user_id)
        )
        return [
            Account(
                account_id=row.account_id,
                user_id=row.user_id,
                account_hash=row.account_hash,
                display_mask=row.display_mask,
                account_type=row.account_type,
                synced_at=row.synced_at,
            )
            for row in result.scalars().all()
        ]

    async def save_positions(self, positions: list[Position]) -> None:
        for position in positions:
            result = await self._session.execute(
                select(PositionRow).where(
                    PositionRow.account_id == position.account_id,
                    PositionRow.symbol == position.symbol,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                self._session.add(
                    PositionRow(
                        position_id=position.position_id,
                        account_id=position.account_id,
                        user_id=position.user_id,
                        symbol=position.symbol,
                        asset_type=position.asset_type.value,
                        quantity=position.quantity,
                        average_price=position.average_price,
                        market_value=position.market_value,
                        current_price=position.current_price,
                        day_change_dollar=position.day_change_dollar,
                        day_change_percent=position.day_change_percent,
                        source_record_id=position.source_record_id,
                        synced_at=position.synced_at,
                    )
                )
            else:
                existing.asset_type = position.asset_type.value
                existing.quantity = position.quantity
                existing.average_price = position.average_price
                existing.market_value = position.market_value
                existing.current_price = position.current_price
                existing.day_change_dollar = position.day_change_dollar
                existing.day_change_percent = position.day_change_percent
                existing.source_record_id = position.source_record_id
                existing.synced_at = position.synced_at
        await self._session.flush()

    async def list_positions(self, user_id: str, account_id: str) -> list[Position]:
        result = await self._session.execute(
            select(PositionRow).where(
                PositionRow.user_id == user_id, PositionRow.account_id == account_id
            )
        )
        return [
            Position(
                position_id=row.position_id,
                account_id=row.account_id,
                user_id=row.user_id,
                symbol=row.symbol,
                asset_type=AssetType(row.asset_type),
                quantity=row.quantity,
                average_price=row.average_price,
                market_value=row.market_value,
                current_price=row.current_price,
                day_change_dollar=row.day_change_dollar,
                day_change_percent=row.day_change_percent,
                source_record_id=row.source_record_id,
                synced_at=row.synced_at,
            )
            for row in result.scalars().all()
        ]

    async def save_balance(self, balance: AccountBalance) -> None:
        self._session.add(
            AccountBalanceRow(
                balance_id=balance.balance_id,
                account_id=balance.account_id,
                user_id=balance.user_id,
                cash_balance=balance.cash_balance,
                schwab_reported_total=balance.schwab_reported_total,
                source_record_id=balance.source_record_id,
                synced_at=balance.synced_at,
            )
        )
        await self._session.flush()

    async def get_latest_balance(self, account_id: str) -> AccountBalance | None:
        result = await self._session.execute(
            select(AccountBalanceRow)
            .where(AccountBalanceRow.account_id == account_id)
            .order_by(AccountBalanceRow.synced_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return AccountBalance(
            balance_id=row.balance_id,
            account_id=row.account_id,
            user_id=row.user_id,
            cash_balance=row.cash_balance,
            schwab_reported_total=row.schwab_reported_total,
            source_record_id=row.source_record_id,
            synced_at=row.synced_at,
        )

    async def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        # Immutable (Docs/DATA_MODEL.md) — always an insert, never an update.
        self._session.add(
            PortfolioSnapshotRow(
                snapshot_id=snapshot.snapshot_id,
                user_id=snapshot.user_id,
                taken_at=snapshot.taken_at,
                total_market_value=snapshot.total_market_value,
                reconciled=snapshot.reconciled,
                reconciliation_diff=snapshot.reconciliation_diff,
                account_ids=snapshot.account_ids,
                warnings=snapshot.warnings,
            )
        )
        await self._session.flush()

    async def get_latest_snapshot(self, user_id: str) -> PortfolioSnapshot | None:
        result = await self._session.execute(
            select(PortfolioSnapshotRow)
            .where(PortfolioSnapshotRow.user_id == user_id)
            .order_by(PortfolioSnapshotRow.taken_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PortfolioSnapshot(
            snapshot_id=row.snapshot_id,
            user_id=row.user_id,
            taken_at=row.taken_at,
            total_market_value=row.total_market_value,
            reconciled=row.reconciled,
            reconciliation_diff=row.reconciliation_diff,
            account_ids=list(row.account_ids),
            warnings=list(row.warnings),
        )

    async def save_raw_response(
        self, raw_response_id: str, payload: dict[str, Any], now: datetime
    ) -> None:
        self._session.add(
            SchwabRawResponseRow(raw_response_id=raw_response_id, payload=payload, created_at=now)
        )
        await self._session.flush()
