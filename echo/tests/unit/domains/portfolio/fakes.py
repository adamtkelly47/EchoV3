from __future__ import annotations

from typing import Any

from core.provenance import ComputedValueRecord
from domains.portfolio.schemas import (
    Account,
    AccountBalance,
    ComplianceResult,
    IPSVersion,
    PortfolioSnapshot,
    Position,
    SchwabCredential,
)


class FakeSchwabCredentialRepository:
    def __init__(self) -> None:
        self._store: dict[str, SchwabCredential] = {}

    async def save(self, credential: SchwabCredential) -> None:
        self._store[credential.user_id] = credential

    async def get_for_user(self, user_id: str) -> SchwabCredential | None:
        return self._store.get(user_id)


class FakePortfolioRepository:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.positions: dict[tuple[str, str], Position] = {}
        self.balances: list[AccountBalance] = []
        self.snapshots: list[PortfolioSnapshot] = []
        self.raw_responses: dict[str, dict[str, Any]] = {}

    async def save_account(self, account: Account) -> Account:
        """Mirrors the real PostgresPortfolioRepository's upsert-by-hash
        contract exactly: an existing account keeps its own stable
        account_id rather than adopting the incoming (freshly-generated)
        one — this fidelity is what let a real production bug (Docs/
        DECISION_LOG.md's Phase 12 entry) be caught by a service-level
        test at all; a fake that just stored whatever it was given would
        have hidden it the same way the bug went live undetected."""
        existing = self.accounts.get(account.account_hash)
        if existing is not None:
            account = account.model_copy(update={"account_id": existing.account_id})
        self.accounts[account.account_hash] = account
        return account

    async def list_accounts(self, user_id: str) -> list[Account]:
        return [a for a in self.accounts.values() if a.user_id == user_id]

    async def save_positions(self, positions: list[Position]) -> None:
        for position in positions:
            self.positions[(position.account_id, position.symbol)] = position

    async def list_positions(self, user_id: str, account_id: str) -> list[Position]:
        return [
            p
            for p in self.positions.values()
            if p.user_id == user_id and p.account_id == account_id
        ]

    async def list_all_positions(self, user_id: str) -> list[Position]:
        return [p for p in self.positions.values() if p.user_id == user_id]

    async def save_balance(self, balance: AccountBalance) -> None:
        self.balances.append(balance)

    async def get_latest_balance(self, account_id: str) -> AccountBalance | None:
        matches = [b for b in self.balances if b.account_id == account_id]
        return matches[-1] if matches else None

    async def list_latest_balances(self, user_id: str) -> list[AccountBalance]:
        latest_by_account: dict[str, AccountBalance] = {}
        for b in self.balances:
            if b.user_id == user_id:
                latest_by_account[b.account_id] = b
        return list(latest_by_account.values())

    async def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        self.snapshots.append(snapshot)

    async def get_latest_snapshot(self, user_id: str) -> PortfolioSnapshot | None:
        matches = [s for s in self.snapshots if s.user_id == user_id]
        return matches[-1] if matches else None

    async def save_raw_response(
        self, raw_response_id: str, payload: dict[str, Any], now: Any
    ) -> None:
        self.raw_responses[raw_response_id] = payload


class FakeIPSRepository:
    def __init__(self) -> None:
        self.versions: list[IPSVersion] = []

    async def save_version(self, version: IPSVersion) -> None:
        """Mirrors the real PostgresIPSRepository's "exactly one active
        version per ips_id" invariant, so a service-level test exercising
        two consecutive edits is meaningful."""
        if version.is_active:
            for existing in self.versions:
                if existing.ips_id == version.ips_id and existing.is_active:
                    idx = self.versions.index(existing)
                    self.versions[idx] = existing.model_copy(update={"is_active": False})
        self.versions.append(version)

    async def get_active(self, user_id: str) -> IPSVersion | None:
        matches = [v for v in self.versions if v.user_id == user_id and v.is_active]
        return matches[-1] if matches else None

    async def get_version(self, version_id: str) -> IPSVersion | None:
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None

    async def list_versions(self, user_id: str) -> list[IPSVersion]:
        return [v for v in self.versions if v.user_id == user_id]


class FakeComplianceResultRepository:
    def __init__(self) -> None:
        self.results: list[ComplianceResult] = []

    async def save(self, result: ComplianceResult) -> None:
        self.results.append(result)

    async def get_latest(self, user_id: str) -> ComplianceResult | None:
        matches = [r for r in self.results if r.user_id == user_id]
        return matches[-1] if matches else None


class FakeSourceRecordRepository:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, record: Any) -> None:
        self.saved.append(record)

    async def get(self, record_id: str) -> Any:
        for record in self.saved:
            if record.record_id == record_id:
                return record
        return None


class FakeComputedValueRecordRepository:
    def __init__(self) -> None:
        self.saved: list[ComputedValueRecord] = []

    async def save(self, record: ComputedValueRecord) -> None:
        self.saved.append(record)

    async def get(self, record_id: str) -> ComputedValueRecord | None:
        for record in self.saved:
            if record.record_id == record_id:
                return record
        return None


class FakeSchwabProvider:
    def __init__(self) -> None:
        self.token_response: dict[str, Any] = {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 1800,
        }
        self.refresh_response: dict[str, Any] = {
            "access_token": "fake-refreshed-token",
            "expires_in": 1800,
        }
        self.account_numbers_response: list[dict[str, Any]] = []
        self.accounts_response: list[dict[str, Any]] = []
        self.quotes_response: dict[str, Any] = {}
        self.price_history_response: dict[str, Any] = {"candles": []}
        self.raise_on_refresh: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def build_authorization_url(self, state: str) -> str:
        self.calls.append(("build_authorization_url", {"state": state}))
        return f"https://api.schwabapi.com/v1/oauth/authorize?state={state}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        self.calls.append(("exchange_code", {"code": code}))
        return self.token_response

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        self.calls.append(("refresh_access_token", {"refresh_token": refresh_token}))
        if self.raise_on_refresh:
            raise self.raise_on_refresh
        return self.refresh_response

    async def get_account_numbers(self, access_token: str) -> list[dict[str, Any]]:
        self.calls.append(("get_account_numbers", {"access_token": access_token}))
        return self.account_numbers_response

    async def get_accounts(self, access_token: str) -> list[dict[str, Any]]:
        self.calls.append(("get_accounts", {"access_token": access_token}))
        return self.accounts_response

    async def get_quotes(self, access_token: str, symbols: list[str]) -> dict[str, Any]:
        self.calls.append(("get_quotes", {"access_token": access_token, "symbols": symbols}))
        return self.quotes_response

    async def get_price_history(self, access_token: str, symbol: str) -> dict[str, Any]:
        self.calls.append(("get_price_history", {"access_token": access_token, "symbol": symbol}))
        return self.price_history_response


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
            {"audit_id": call_id, "action": action, "result": result, "detail": detail}
        )
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e.get("correlation_id") == correlation_id]
