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
from core.provenance import ComputedValueRecord, SourceRecord, ValidationStatus
from core.time import Clock
from domains.portfolio.errors import (
    HypotheticalTradeAlreadyClosedError,
    HypotheticalTradeNotFoundError,
    NoActiveIPSError,
    PortfolioSnapshotNotFoundError,
    QuotePriceUnavailableError,
    SchwabCredentialNotFoundError,
    SchwabReauthorizationRequiredError,
    SchwabTokenRefreshError,
)
from domains.portfolio.models import HypotheticalTradeAction, HypotheticalTradeStatus
from domains.portfolio.policies import (
    build_snapshot,
    compare_against_no_action,
    compute_asset_class_exposure,
    compute_concentration_warnings,
    compute_cross_account_exposure,
    compute_gain_loss,
    compute_hypothetical_gain_loss_percent,
    compute_position_weights,
    compute_sector_exposure,
    days_to_realize,
    evaluate_compliance,
    extract_code_from_redirect,
    generate_oauth_state,
    is_refresh_token_expired,
    is_snapshot_stale,
    needs_refresh,
    parse_account,
    parse_balance,
    parse_positions,
    parse_price_history,
    parse_quote,
    reconcile,
    thesis_direction_correct,
    validate_ips_rules,
    verify_oauth_state,
)
from domains.portfolio.repository import (
    ComplianceResultRepository,
    HypotheticalTradeRepository,
    IPSRepository,
    PortfolioRepository,
    SchwabCredentialRepository,
)
from domains.portfolio.schemas import (
    Account,
    AllocationRange,
    ComplianceResult,
    ConcentrationRule,
    HypotheticalPerformanceSample,
    HypotheticalTrade,
    HypotheticalTradeEvaluation,
    IPSVersion,
    MoneyDashboard,
    PortfolioSnapshot,
    PriceHistoryPoint,
    Quote,
    RestrictedSecurity,
    SchwabCredential,
)
from infrastructure.database.repositories.audit import AuditRepository
from infrastructure.database.repositories.provenance import (
    ComputedValueRecordRepository,
    SourceRecordRepository,
)
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
        computed_values: ComputedValueRecordRepository,
        ips: IPSRepository,
        compliance_results: ComplianceResultRepository,
        hypothetical_trades: HypotheticalTradeRepository,
    ) -> None:
        self._credentials = credentials
        self._portfolio = portfolio
        self._source_records = source_records
        self._provider = provider
        self._cipher = cipher
        self._audit = audit
        self._clock = clock
        self._state_secret = state_secret
        self._computed_values = computed_values
        self._ips = ips
        self._compliance_results = compliance_results
        self._hypothetical_trades = hypothetical_trades

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

    async def is_connected(self, user_id: str) -> bool:
        """PROMPT.md Phase 22 implement item 6: "integration status." A
        credential existing is the real, honest signal available here —
        never a live Schwab health check on every dashboard load."""
        return await self._credentials.get_for_user(user_id) is not None

    async def get_dashboard(self, user_id: str) -> MoneyDashboard:
        """PROMPT.md Phase 13: turns the latest already-synced, reconciled
        snapshot into deterministic analysis. Never triggers a live Schwab
        call itself — every displayed number traces back to that snapshot
        and the position rows it was built from (verification item 1)."""
        snapshot = await self._portfolio.get_latest_snapshot(user_id)
        if snapshot is None:
            raise PortfolioSnapshotNotFoundError(
                f"no synced portfolio snapshot for user {user_id!r} "
                "— run POST /portfolio/sync first"
            )
        positions = await self._portfolio.list_all_positions(user_id)
        now = self._clock.now_utc()

        # An active IPS's own concentration rule (PROMPT.md Phase 14)
        # supersedes Phase 13's generic default the moment one exists — the
        # promise made in that phase's own code comment.
        active_ips = await self._ips.get_active(user_id)
        concentration_threshold = (
            active_ips.concentration_rule.max_position_percent if active_ips is not None else None
        )

        weights = compute_position_weights(positions, snapshot.total_market_value)
        asset_class_exposure = compute_asset_class_exposure(positions, snapshot.total_market_value)
        sector_exposure = compute_sector_exposure(snapshot.total_market_value)
        cross_account_exposure = compute_cross_account_exposure(positions)
        concentration_warnings = (
            compute_concentration_warnings(weights, threshold_percent=concentration_threshold)
            if concentration_threshold is not None
            else compute_concentration_warnings(weights)
        )
        gain_loss, total_gain_loss = compute_gain_loss(positions)

        warnings = list(snapshot.warnings)
        missing_cost_basis = sum(1 for p in positions if p.average_price is None)
        if missing_cost_basis:
            warnings.append(
                f"{missing_cost_basis} position(s) missing cost basis "
                "— excluded from unrealized gain/loss, not estimated"
            )
        warnings.append(
            "sector exposure is a single 'Unknown' bucket — real sector classification "
            "requires the Research domain (PROMPT.md Phase 16+), not yet available"
        )

        input_record_ids = sorted({snapshot.snapshot_id, *(p.source_record_id for p in positions)})
        record = ComputedValueRecord(
            calculation_name="portfolio.money_dashboard",
            calculation_version="1",
            input_record_ids=input_record_ids,
            executed_at=now,
            output={
                "total_market_value": snapshot.total_market_value,
                "position_count": len(positions),
            },
            rounding_policy=(
                "dollar amounts rounded to 2 decimal places; percentages rounded to 2 "
                "decimal places (hundredths of a percent)"
            ),
            validation_result=ValidationStatus.PASSED,
        )
        await self._computed_values.save(record)

        return MoneyDashboard(
            user_id=user_id,
            generated_at=now,
            last_verified_sync_at=snapshot.taken_at,
            is_stale=is_snapshot_stale(snapshot.taken_at, now),
            total_market_value=snapshot.total_market_value,
            reconciled=snapshot.reconciled,
            position_weights=weights,
            asset_class_exposure=asset_class_exposure,
            sector_exposure=sector_exposure,
            cross_account_exposure=cross_account_exposure,
            concentration_warnings=concentration_warnings,
            unrealized_gain_loss=gain_loss,
            total_unrealized_gain_loss_dollar=total_gain_loss,
            warnings=warnings,
            computed_value_record_id=record.record_id,
        )

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

    async def create_ips_version(
        self,
        user_id: str,
        ips_id: str | None,
        account_ids: list[str],
        allocation_ranges: list[AllocationRange],
        concentration_rule: ConcentrationRule,
        restricted_securities: list[RestrictedSecurity],
    ) -> IPSVersion:
        """PROMPT.md Phase 14 implement items 1-3 ("IPS schema", "IPS
        editor", "versioning"). `ips_id=None` starts a brand-new document;
        passing an existing `ips_id` supersedes its current active version
        with a new one — the prior version's own rules are never rewritten
        (verification 3), only which version is active changes."""
        validate_ips_rules(allocation_ranges, restricted_securities)
        now = self._clock.now_utc()
        if ips_id is None:
            ips_id = new_id("ips")
            version_number = 1
        else:
            existing_versions = await self._ips.list_versions(user_id)
            matching = [v for v in existing_versions if v.ips_id == ips_id]
            version_number = (max((v.version_number for v in matching), default=0)) + 1
        version = IPSVersion(
            ips_id=ips_id,
            version_number=version_number,
            user_id=user_id,
            account_ids=account_ids,
            allocation_ranges=allocation_ranges,
            concentration_rule=concentration_rule,
            restricted_securities=restricted_securities,
            created_at=now,
            is_active=True,
        )
        await self._ips.save_version(version)
        await self._audit.record(
            action="portfolio.ips_version_created",
            result="success",
            detail={"user_id": user_id, "ips_id": ips_id, "version_number": version_number},
        )
        return version

    async def get_active_ips(self, user_id: str) -> IPSVersion | None:
        return await self._ips.get_active(user_id)

    async def list_ips_versions(self, user_id: str) -> list[IPSVersion]:
        return await self._ips.list_versions(user_id)

    async def evaluate_ips_compliance(self, user_id: str) -> ComplianceResult:
        """PROMPT.md Phase 14 implement items 8-9 ("rule evaluation",
        "compliance results"). Deterministic (verification 1) and always
        cites exactly which IPS version and portfolio snapshot it was
        evaluated against (verification 2) — never a live Schwab call, only
        the latest already-synced data, matching Phase 13's dashboard."""
        active_ips = await self._ips.get_active(user_id)
        if active_ips is None:
            raise NoActiveIPSError(
                f"no active IPS for user {user_id!r} — create one before evaluating compliance"
            )
        snapshot = await self._portfolio.get_latest_snapshot(user_id)
        if snapshot is None:
            raise PortfolioSnapshotNotFoundError(
                f"no synced portfolio snapshot for user {user_id!r} "
                "— run POST /portfolio/sync first"
            )
        positions = await self._portfolio.list_all_positions(user_id)
        balances = await self._portfolio.list_latest_balances(user_id)
        breaches = evaluate_compliance(active_ips, positions, balances)

        result = ComplianceResult(
            user_id=user_id,
            ips_version_id=active_ips.version_id,
            snapshot_id=snapshot.snapshot_id,
            evaluated_at=self._clock.now_utc(),
            compliant=not breaches,
            breaches=breaches,
        )
        await self._compliance_results.save(result)
        await self._audit.record(
            action="portfolio.ips_compliance_evaluated",
            result="success",
            detail={
                "user_id": user_id,
                "ips_version_id": active_ips.version_id,
                "snapshot_id": snapshot.snapshot_id,
                "compliant": result.compliant,
                "breach_count": len(breaches),
            },
        )
        return result

    async def get_latest_compliance_result(self, user_id: str) -> ComplianceResult | None:
        """PROMPT.md Phase 14 implement item 10 ("drift dashboard"): the
        latest already-evaluated compliance result — like the money
        dashboard, this reads, it never re-evaluates on the caller's behalf
        (call `evaluate_ips_compliance` explicitly for that, mirroring
        `sync`/`get_dashboard`'s own read/write split)."""
        return await self._compliance_results.get_latest(user_id)

    # --- PROMPT.md Phase 27: paper trading observation. No method here (or
    # anywhere else in this service, this Protocol, or providers/schwab/
    # adapter.py) ever places, modifies, or cancels a real order — the same
    # "No trading endpoint is implemented... enforced by omission" guarantee
    # this module's own docstring already states for Phase 12, restated
    # here because it applies with equal force to this phase's own new
    # methods: they only ever call `get_quotes` (an existing, already-real
    # read-only market-data call), never anything execution-capable. ---

    async def propose_hypothetical_trade(
        self,
        user_id: str,
        *,
        symbol: str,
        action: HypotheticalTradeAction,
        quantity: float,
        rationale: str,
        expected_outcome: str,
        expected_horizon_days: int,
        rationale_references: list[str] | None = None,
    ) -> HypotheticalTrade:
        """PROMPT.md Phase 27 capabilities 1-3: "create hypothetical trade
        proposals," "record rationale," "record expected outcome." The
        reference price is a real, just-fetched quote — never a
        user-supplied or invented number — so every subsequent performance
        calculation traces back to an actual market observation."""
        price = await self._require_current_price(user_id, symbol)
        trade = HypotheticalTrade(
            user_id=user_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            hypothetical_price=price,
            rationale=rationale,
            rationale_references=rationale_references or [],
            expected_outcome=expected_outcome,
            expected_horizon_days=expected_horizon_days,
            proposed_at=self._clock.now_utc(),
        )
        await self._hypothetical_trades.save_trade(trade)
        await self._audit.record(
            action="portfolio.hypothetical_trade_proposed",
            result="success",
            detail={"trade_id": trade.trade_id, "symbol": symbol, "action": action.value},
        )
        return trade

    async def get_hypothetical_trade(self, trade_id: str) -> HypotheticalTrade:
        return await self._require_hypothetical_trade(trade_id)

    async def list_hypothetical_trades_for_user(self, user_id: str) -> list[HypotheticalTrade]:
        return await self._hypothetical_trades.list_trades_for_user(user_id)

    async def record_hypothetical_performance_sample(
        self, trade_id: str
    ) -> HypotheticalPerformanceSample:
        """PROMPT.md Phase 27 capability 4: "track hypothetical
        performance." One real market observation at a time — on demand,
        matching Phase 24's own "on-demand evaluate" precedent, rather than
        a new monitor type built ahead of any demonstrated need for one."""
        trade = await self._require_hypothetical_trade(trade_id)
        price = await self._require_current_price(trade.user_id, trade.symbol)
        now = self._clock.now_utc()
        sample = HypotheticalPerformanceSample(
            trade_id=trade_id,
            observed_at=now,
            price=price,
            gain_loss_percent=compute_hypothetical_gain_loss_percent(
                trade.action, trade.hypothetical_price, price
            ),
        )
        await self._hypothetical_trades.save_performance_sample(sample)
        return sample

    async def close_hypothetical_trade(
        self, trade_id: str, *, review_note: str
    ) -> HypotheticalTrade:
        """PROMPT.md Phase 27 capability 8: "review failures." A one-time,
        terminal transition — a human's own assessment of what actually
        happened, recorded alongside the real closing price, never
        overwritten."""
        trade = await self._require_hypothetical_trade(trade_id)
        if trade.status == HypotheticalTradeStatus.CLOSED:
            raise HypotheticalTradeAlreadyClosedError(
                f"hypothetical trade {trade_id!r} is already closed"
            )
        closing_price = await self._require_current_price(trade.user_id, trade.symbol)
        closed = trade.model_copy(
            update={
                "status": HypotheticalTradeStatus.CLOSED,
                "review_note": review_note,
                "reviewed_at": self._clock.now_utc(),
                "closing_price": closing_price,
            }
        )
        await self._hypothetical_trades.save_trade(closed)
        await self._audit.record(
            action="portfolio.hypothetical_trade_closed",
            result="success",
            detail={"trade_id": trade_id},
        )
        return closed

    async def evaluate_hypothetical_trade(self, trade_id: str) -> HypotheticalTradeEvaluation:
        """PROMPT.md Phase 27 capabilities 5-7: "compare against no
        action," "measure thesis quality," "measure timing." Computed
        fresh from the trade and its stored samples on every call — never
        itself a stored fact, matching `MoneyDashboard`/`ComplianceResult`'s
        own "computed, not asserted" discipline. Once a trade is closed,
        its recorded `closing_price` is the authoritative final
        observation; while still open, the latest performance sample is."""
        trade = await self._require_hypothetical_trade(trade_id)
        samples = await self._hypothetical_trades.list_performance_samples(trade_id)
        latest_sample = max(samples, key=lambda s: s.observed_at) if samples else None

        reference_price = (
            trade.closing_price
            if trade.closing_price is not None
            else (latest_sample.price if latest_sample is not None else None)
        )
        gain_loss_percent = (
            compute_hypothetical_gain_loss_percent(
                trade.action, trade.hypothetical_price, reference_price
            )
            if reference_price is not None
            else None
        )
        return HypotheticalTradeEvaluation(
            trade=trade,
            latest_sample=latest_sample,
            gain_loss_percent=gain_loss_percent,
            comparison_vs_no_action_percent=(
                compare_against_no_action(gain_loss_percent)
                if gain_loss_percent is not None
                else None
            ),
            thesis_direction_correct=(
                thesis_direction_correct(trade.action, trade.hypothetical_price, reference_price)
                if reference_price is not None
                else None
            ),
            days_to_realize=days_to_realize(
                trade.action, trade.hypothetical_price, trade.proposed_at, samples
            ),
        )

    async def _require_current_price(self, user_id: str, symbol: str) -> float:
        quotes = await self.get_quotes(user_id, [symbol])
        if not quotes or quotes[0].price is None:
            raise QuotePriceUnavailableError(f"no current price available for {symbol!r}")
        return quotes[0].price

    async def _require_hypothetical_trade(self, trade_id: str) -> HypotheticalTrade:
        trade = await self._hypothetical_trades.get_trade(trade_id)
        if trade is None:
            raise HypotheticalTradeNotFoundError(
                f"no hypothetical trade found with id {trade_id!r}"
            )
        return trade

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
