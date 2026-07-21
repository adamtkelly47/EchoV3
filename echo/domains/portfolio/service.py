"""Portfolio's aggregate-lifecycle owner. `PortfolioProviderPort` is defined
here (not in providers/), matching domains/calendar/service.py's
`CalendarProviderPort` precedent: the domain owns the port, speaks to it in
primitives (raw dicts — Schwab's actual JSON), and does its own translation
into typed schemas (domains/portfolio/policies.py) — so the concrete
provider adapter never needs to import anything from domains/
(scripts/check_architecture.py's providers-must-not-import-domains rule).

PROMPT.md Phase 12 verification 5: "No trading endpoint is implemented."
This is enforced by omission — no method on this Protocol, this service, or
providers/schwab/adapter.py ever places, modifies, or cancels an order.
Schwab has no separate read-only OAuth product (unlike Google Calendar's
calendar.readonly), so this is the only place that guarantee can actually
be enforced: the granted token is technically trade-capable, but nothing in
this codebase ever calls a trading endpoint with it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

from core.errors import EchoError
from core.identifiers import new_id
from core.provenance import SourceRecord, ValidationStatus
from core.time import Clock
from domains.portfolio.errors import (
    SchwabCredentialNotFoundError,
    SchwabReauthorizationRequiredError,
    SchwabTokenRefreshError,
)
from domains.portfolio.policies import (
    build_snapshot,
    extract_code_from_redirect,
    generate_oauth_state,
    is_refresh_token_expired,
    needs_refresh,
    parse_account,
    parse_balance,
    parse_positions,
    parse_price_history,
    parse_quote,
    reconcile,
    verify_oauth_state,
)
from domains.portfolio.repository import PortfolioRepository, SchwabCredentialRepository
from domains.portfolio.schemas import (
    Account,
    PortfolioSnapshot,
    PriceHistoryPoint,
    Quote,
    SchwabCredential,
)
from infrastructure.database.repositories.audit import AuditRepository
from infrastructure.database.repositories.provenance import SourceRecordRepository
from infrastructure.secrets.encryption import SecretCipher


class PortfolioProviderPort(Protocol):
    def build_authorization_url(self, state: str) -> str: ...
    async def exchange_code(self, code: str) -> dict[str, Any]: ...
    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]: ...
    async def get_account_numbers(self, access_token: str) -> list[dict[str, Any]]: ...
    async def get_accounts(self, access_token: str) -> list[dict[str, Any]]: ...
    async def get_quotes(self, access_token: str, symbols: list[str]) -> dict[str, Any]: ...
    async def get_price_history(self, access_token: str, symbol: str) -> dict[str, Any]: ...


class PortfolioService:
    def __init__(
        self,
        credentials: SchwabCredentialRepository,
        portfolio: PortfolioRepository,
        source_records: SourceRecordRepository,
        provider: PortfolioProviderPort,
        cipher: SecretCipher,
        audit: AuditRepository,
        clock: Clock,
        state_secret: str,
    ) -> None:
        self._credentials = credentials
        self._portfolio = portfolio
        self._source_records = source_records
        self._provider = provider
        self._cipher = cipher
        self._audit = audit
        self._clock = clock
        self._state_secret = state_secret

    def start_authorization(self, user_id: str) -> str:
        state = generate_oauth_state(user_id, new_id(), self._clock.now_utc(), self._state_secret)
        return self._provider.build_authorization_url(state)

    async def complete_authorization(self, redirect_value: str, state: str) -> SchwabCredential:
        """`redirect_value` is either the bare `code` or the full dead-page
        URL the user copied by hand (Schwab's fixed callback is never
        actually reachable — see this module's own docstring)."""
        user_id = verify_oauth_state(state, self._state_secret, self._clock.now_utc())
        code = extract_code_from_redirect(redirect_value)
        raw = await self._provider.exchange_code(code)
        now = self._clock.now_utc()
        credential = SchwabCredential(
            user_id=user_id,
            encrypted_access_token=self._cipher.encrypt(raw["access_token"]),
            encrypted_refresh_token=self._cipher.encrypt(raw["refresh_token"]),
            access_token_expires_at=now + timedelta(seconds=raw["expires_in"]),
            # Verified against Schwab's own documented token lifetime, not
            # assumed (Docs/DECISION_LOG.md's Phase 12 entry) — a hard
            # 7-day limit with no programmatic renewal.
            refresh_token_expires_at=now + timedelta(days=7),
            created_at=now,
            updated_at=now,
        )
        await self._credentials.save(credential)
        await self._audit.record(
            action="schwab.connected", result="success", detail={"user_id": user_id}
        )
        return credential

    async def sync(self, user_id: str) -> PortfolioSnapshot:
        """PROMPT.md Phase 12 implement items 3-13 in one pipeline: discover
        accounts, fetch balances/positions, normalize, store raw responses
        and provenance, reconcile, and produce an immutable snapshot."""
        access_token = await self._get_valid_access_token(user_id)
        now = self._clock.now_utc()
        warnings: list[str] = []

        raw_accounts = await self._provider.get_accounts(access_token)
        account_hashes = await self._provider.get_account_numbers(access_token)
        hash_by_number = {h.get("accountNumber"): h.get("hashValue") for h in account_hashes}

        account_ids: list[str] = []
        all_positions = []
        all_balances = []
        for raw_account in raw_accounts:
            security_account = raw_account.get("securitiesAccount", raw_account)
            real_number = security_account.get("accountNumber")
            account_hash = hash_by_number.get(real_number)
            if account_hash is None:
                warnings.append("could not resolve an account hash for one account — skipped")
                continue

            source_record_id = await self._store_raw_response(
                raw_account, provider="schwab", now=now
            )
            parsed_account = parse_account(
                raw_account, user_id=user_id, account_hash=account_hash, synced_at=now
            )
            # save_account returns the *persisted* account — its account_id
            # is stable across syncs when this account_hash already existed,
            # unlike parsed_account's freshly-generated one (Docs/
            # DECISION_LOG.md's Phase 12 entry: using the wrong one here
            # silently orphaned a new set of position/balance rows every
            # sync instead of ever updating the same ones).
            account = await self._portfolio.save_account(parsed_account)
            account_ids.append(account.account_id)

            balance = parse_balance(
                raw_account,
                account_id=account.account_id,
                user_id=user_id,
                source_record_id=source_record_id,
                synced_at=now,
            )
            await self._portfolio.save_balance(balance)
            all_balances.append(balance)

            positions = parse_positions(
                raw_account,
                account_id=account.account_id,
                user_id=user_id,
                source_record_id=source_record_id,
                synced_at=now,
            )
            await self._portfolio.save_positions(positions)
            all_positions.extend(positions)

            _, _, account_warnings = reconcile(positions, balance)
            warnings.extend(account_warnings)

        snapshot = build_snapshot(user_id, now, account_ids, all_positions, all_balances, warnings)
        await self._portfolio.save_snapshot(snapshot)
        await self._audit.record(
            action="schwab.synced",
            result="success",
            detail={
                "user_id": user_id,
                "account_count": len(account_ids),
                "reconciled": snapshot.reconciled,
            },
        )
        return snapshot

    async def get_accounts(self, user_id: str) -> list[Account]:
        return await self._portfolio.list_accounts(user_id)

    async def get_latest_snapshot(self, user_id: str) -> PortfolioSnapshot | None:
        return await self._portfolio.get_latest_snapshot(user_id)

    async def get_quotes(self, user_id: str, symbols: list[str]) -> list[Quote]:
        access_token = await self._get_valid_access_token(user_id)
        now = self._clock.now_utc()
        raw = await self._provider.get_quotes(access_token, symbols)
        source_record_id = await self._store_raw_response(raw, provider="schwab", now=now)
        return [
            parse_quote(
                raw.get(symbol, {}),
                symbol=symbol,
                source_record_id=source_record_id,
                retrieved_at=now,
            )
            for symbol in symbols
        ]

    async def get_price_history(self, user_id: str, symbol: str) -> list[PriceHistoryPoint]:
        access_token = await self._get_valid_access_token(user_id)
        raw = await self._provider.get_price_history(access_token, symbol)
        return parse_price_history(raw)

    async def _store_raw_response(
        self, raw: dict[str, Any], *, provider: str, now: datetime
    ) -> str:
        """PROMPT.md Phase 12 implement item 9: raw response storage
        policy. Stores the raw payload (domain-owned) and a platform-wide
        SourceRecord pointing at it (core.provenance, Phase 4) — the one
        place "where did this number come from?" can be answered from."""
        raw_response_id = new_id("schwabraw")
        await self._portfolio.save_raw_response(raw_response_id, raw, now)
        record = SourceRecord(
            source_type="brokerage-api",
            provider=provider,
            retrieved_at=now,
            origin="schwab-trader-api",
            raw_storage_ref=raw_response_id,
            parser_version="1",
            validation_status=ValidationStatus.PASSED,
        )
        await self._source_records.save(record)
        return record.record_id

    async def _get_valid_access_token(self, user_id: str) -> str:
        credential = await self._credentials.get_for_user(user_id)
        if credential is None:
            raise SchwabCredentialNotFoundError(f"no Schwab connection for user {user_id!r}")

        now = self._clock.now_utc()
        if not needs_refresh(credential, now):
            return self._cipher.decrypt(credential.encrypted_access_token)

        if is_refresh_token_expired(credential, now):
            raise SchwabReauthorizationRequiredError(
                f"Schwab refresh token for user {user_id!r} expired — reconnect required"
            )

        refresh_token = self._cipher.decrypt(credential.encrypted_refresh_token)
        try:
            raw = await self._provider.refresh_access_token(refresh_token)
        except EchoError as exc:
            await self._audit.record(
                action="schwab.token_refresh_failed", result="failure", detail={"user_id": user_id}
            )
            raise SchwabTokenRefreshError(f"could not refresh Schwab token: {exc}") from exc

        updated = credential.model_copy(
            update={
                "encrypted_access_token": self._cipher.encrypt(raw["access_token"]),
                "access_token_expires_at": now + timedelta(seconds=raw["expires_in"]),
                "updated_at": now,
            }
        )
        await self._credentials.save(updated)
        await self._audit.record(
            action="schwab.token_refreshed", result="success", detail={"user_id": user_id}
        )
        return self._cipher.decrypt(updated.encrypted_access_token)
