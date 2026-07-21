"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as domains/calendar/policies.py.
This is also where Schwab's raw JSON (returned as plain dicts by
domains.portfolio.service.PortfolioProviderPort, matching the Calendar/
Approvals precedent of providers speaking in primitives so providers/ never
imports domains/) gets translated into Portfolio's own typed schemas —
CONSTITUTION.md's Mandatory Provider Normalization: "The Portfolio Domain
shall never receive a Schwab SDK object."

Field names (`securitiesAccount`, `currentBalances`, `positions`,
`instrument`, `longQuantity`/`shortQuantity`, `marketValue`, `averagePrice`,
`liquidationValue`) were corroborated across multiple independent real
Schwab API integration sources before writing this file (CONSTITUTION.md:
Provider Due Diligence) — Schwab's own reference docs require an
authenticated developer login and could not be fetched directly, so these
were additionally re-verified against the real, live connected account
during Phase 12's live testing (Docs/DECISION_LOG.md's Phase 12 entry) —
not trusted from secondhand sources alone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

from domains.portfolio.errors import (
    IPSValidationError,
    SchwabOAuthStateInvalidError,
    SchwabRedirectValueInvalidError,
)
from domains.portfolio.models import AssetType
from domains.portfolio.schemas import (
    Account,
    AccountBalance,
    AllocationRange,
    AssetClassExposure,
    ComplianceBreach,
    ConcentrationWarning,
    IPSVersion,
    PortfolioSnapshot,
    Position,
    PositionGainLoss,
    PositionWeight,
    PriceHistoryPoint,
    Quote,
    RestrictedSecurity,
    SchwabCredential,
    SectorExposure,
    SymbolExposure,
)

# A rounding-error tolerance, not a "close enough" fudge on real
# discrepancies (PROMPT.md Phase 12 verification 1: "account totals
# reconcile") — cents-level floating point noise, nothing more.
_RECONCILIATION_TOLERANCE = 0.01

# Rounding policy (PROMPT.md Phase 13 verification item 3, "rounding rules
# are documented"): dollar amounts round to whole cents, percentages round
# to hundredths of a percent. Consistent with the float-based money
# arithmetic already established throughout this module (no Decimal
# conversion — introducing one here for calculations only, while every
# other money field in this codebase stays float, would be an inconsistent
# half-migration rather than a real improvement).
_MONEY_DECIMALS = 2
_PERCENT_DECIMALS = 2

# A generic concentration threshold — this is Portfolio's own default
# business rule (Docs/DOMAIN_OWNERSHIP.md: Portfolio owns "concentration
# limits"), used until an Investment Policy Statement (PROMPT.md Phase 14)
# can supply a user-specific one.
_DEFAULT_CONCENTRATION_THRESHOLD_PERCENT = 10.0

# Sector classification is Research-domain fundamental data
# (Docs/DOMAIN_OWNERSHIP.md: Research owns "Fundamental Data"; Portfolio
# does not), and Research isn't built until PROMPT.md Phase 16 — so every
# position is reported under a single "Unknown" sector bucket for now
# rather than a fabricated mapping.
_UNKNOWN_SECTOR = "Unknown"

# PROMPT.md Phase 13 verification item 5: "dashboard clearly shows last
# verified sync time" — data older than this is flagged stale, not
# silently presented as current.
_STALENESS_THRESHOLD = timedelta(hours=24)

# Schwab's `instrument.assetType` is a broad category — verified live
# (Docs/DECISION_LOG.md's Phase 12 entry) that ETFs report
# assetType="COLLECTIVE_INVESTMENT", the same broad bucket a mutual fund
# would likely use, with the actually-distinguishing classification in the
# separate, more specific `instrument.type` field. `_INSTRUMENT_TYPE_MAP` is
# checked first; `_ASSET_TYPE_MAP` is the fallback for instruments that
# don't have (or don't need) that finer-grained field, e.g. plain equities.
_ASSET_TYPE_MAP = {
    "EQUITY": AssetType.EQUITY,
    "OPTION": AssetType.OPTION,
    "MUTUAL_FUND": AssetType.MUTUAL_FUND,
    "FIXED_INCOME": AssetType.FIXED_INCOME,
    "CASH_EQUIVALENT": AssetType.CASH_EQUIVALENT,
}

_INSTRUMENT_TYPE_MAP = {
    "EXCHANGE_TRADED_FUND": AssetType.ETF,
}


def needs_refresh(
    credential: SchwabCredential, now: datetime, buffer: timedelta = timedelta(minutes=5)
) -> bool:
    return now >= (credential.access_token_expires_at - buffer)


def is_refresh_token_expired(credential: SchwabCredential, now: datetime) -> bool:
    """Schwab's refresh token has a hard 7-day expiry with no programmatic
    renewal — this is checked *before* attempting a refresh, so a doomed
    refresh call is never made; the caller gets an honest "reconnect"
    signal instead of a generic provider failure."""
    return now >= credential.refresh_token_expires_at


def mask_account_number(real_account_number: str) -> str:
    """The real number is used only long enough to compute this mask
    (PROMPT.md Phase 12 verification 6) — never persisted, logged, or
    returned from any API response."""
    last_four = real_account_number[-4:] if len(real_account_number) >= 4 else real_account_number
    return f"••••{last_four}"


def parse_account(
    raw: dict[str, Any], *, user_id: str, account_hash: str, synced_at: datetime
) -> Account:
    security_account = raw.get("securitiesAccount", raw)
    real_account_number = str(security_account.get("accountNumber", ""))
    return Account(
        user_id=user_id,
        account_hash=account_hash,
        display_mask=mask_account_number(real_account_number),
        account_type=str(security_account.get("type", "unknown")),
        synced_at=synced_at,
    )


def parse_balance(
    raw: dict[str, Any],
    *,
    account_id: str,
    user_id: str,
    source_record_id: str,
    synced_at: datetime,
) -> AccountBalance:
    security_account = raw.get("securitiesAccount", raw)
    balances = security_account.get("currentBalances", {})
    return AccountBalance(
        account_id=account_id,
        user_id=user_id,
        cash_balance=balances.get("cashBalance"),
        schwab_reported_total=balances.get("liquidationValue"),
        source_record_id=source_record_id,
        synced_at=synced_at,
    )


def parse_positions(
    raw: dict[str, Any],
    *,
    account_id: str,
    user_id: str,
    source_record_id: str,
    synced_at: datetime,
) -> list[Position]:
    security_account = raw.get("securitiesAccount", raw)
    positions = []
    for raw_position in security_account.get("positions", []):
        instrument = raw_position.get("instrument", {})
        long_qty = raw_position.get("longQuantity", 0) or 0
        short_qty = raw_position.get("shortQuantity", 0) or 0
        asset_type = _INSTRUMENT_TYPE_MAP.get(instrument.get("type", ""))
        if asset_type is None:
            asset_type = _ASSET_TYPE_MAP.get(instrument.get("assetType", ""), AssetType.OTHER)
        positions.append(
            Position(
                account_id=account_id,
                user_id=user_id,
                symbol=str(instrument.get("symbol", "")),
                asset_type=asset_type,
                quantity=long_qty - short_qty,
                average_price=raw_position.get("averagePrice"),
                market_value=raw_position.get("marketValue"),
                current_price=instrument.get("closingPrice"),
                day_change_dollar=raw_position.get("currentDayProfitLoss"),
                day_change_percent=raw_position.get("currentDayProfitLossPercentage"),
                source_record_id=source_record_id,
                synced_at=synced_at,
            )
        )
    return positions


def parse_quote(
    raw: dict[str, Any], *, symbol: str, source_record_id: str, retrieved_at: datetime
) -> Quote:
    quote_data = raw.get("quote", raw)
    return Quote(
        symbol=symbol,
        price=quote_data.get("lastPrice"),
        change_dollar=quote_data.get("netChange"),
        change_percent=quote_data.get("netPercentChange"),
        retrieved_at=retrieved_at,
        source_record_id=source_record_id,
    )


def parse_price_history(raw: dict[str, Any]) -> list[PriceHistoryPoint]:
    points = []
    for candle in raw.get("candles", []):
        epoch_ms = candle.get("datetime")
        if epoch_ms is None:
            continue
        points.append(
            PriceHistoryPoint(
                timestamp=datetime.fromtimestamp(epoch_ms / 1000, tz=UTC),
                open=candle["open"],
                high=candle["high"],
                low=candle["low"],
                close=candle["close"],
                volume=candle["volume"],
            )
        )
    return points


def reconcile(
    positions: list[Position], balance: AccountBalance
) -> tuple[bool, float | None, list[str]]:
    """PROMPT.md Phase 12 verification 1/2: "account totals reconcile" /
    "position market values reconcile." Compares Echo's own sum of
    normalized position market values + cash against Schwab's own reported
    total — a real consistency check, not a trust-and-hope."""
    warnings: list[str] = []
    positions_with_value = [p for p in positions if p.market_value is not None]
    if len(positions_with_value) != len(positions):
        warnings.append(
            f"{len(positions) - len(positions_with_value)} position(s) missing market_value "
            "— excluded from reconciliation, not estimated"
        )

    if balance.schwab_reported_total is None or balance.cash_balance is None:
        warnings.append("Schwab did not report a total/cash balance — reconciliation skipped")
        return False, None, warnings

    computed_total = balance.cash_balance + sum(p.market_value or 0.0 for p in positions_with_value)
    diff = round(computed_total - balance.schwab_reported_total, 2)
    reconciled = abs(diff) <= _RECONCILIATION_TOLERANCE
    if not reconciled:
        warnings.append(
            f"reconciliation mismatch: computed total {computed_total} vs. "
            f"Schwab-reported {balance.schwab_reported_total} (diff {diff})"
        )
    return reconciled, diff, warnings


def build_snapshot(
    user_id: str,
    taken_at: datetime,
    account_ids: list[str],
    all_positions: list[Position],
    all_balances: list[AccountBalance],
    extra_warnings: list[str],
) -> PortfolioSnapshot:
    total_market_value = sum(b.cash_balance or 0.0 for b in all_balances) + sum(
        p.market_value or 0.0 for p in all_positions
    )
    schwab_total = sum(b.schwab_reported_total or 0.0 for b in all_balances)
    diff = round(total_market_value - schwab_total, 2) if all_balances else None
    reconciled = diff is not None and abs(diff) <= _RECONCILIATION_TOLERANCE
    return PortfolioSnapshot(
        user_id=user_id,
        taken_at=taken_at,
        total_market_value=total_market_value,
        reconciled=reconciled,
        reconciliation_diff=diff,
        account_ids=account_ids,
        warnings=extra_warnings,
    )


def compute_position_weights(
    positions: list[Position], total_market_value: float
) -> list[PositionWeight]:
    """Positions missing `market_value` are excluded, not treated as zero
    (PROMPT.md Phase 13 verification 4: never estimate missing data)."""
    weights = []
    for p in positions:
        if p.market_value is None:
            continue
        weight_percent = (
            round(p.market_value / total_market_value * 100, _PERCENT_DECIMALS)
            if total_market_value
            else 0.0
        )
        weights.append(
            PositionWeight(
                symbol=p.symbol,
                account_id=p.account_id,
                market_value=round(p.market_value, _MONEY_DECIMALS),
                weight_percent=weight_percent,
            )
        )
    return weights


def compute_asset_class_exposure(
    positions: list[Position], total_market_value: float
) -> list[AssetClassExposure]:
    totals: dict[AssetType, float] = {}
    for p in positions:
        if p.market_value is None:
            continue
        totals[p.asset_type] = totals.get(p.asset_type, 0.0) + p.market_value
    return [
        AssetClassExposure(
            asset_type=asset_type,
            market_value=round(value, _MONEY_DECIMALS),
            weight_percent=(
                round(value / total_market_value * 100, _PERCENT_DECIMALS)
                if total_market_value
                else 0.0
            ),
        )
        for asset_type, value in totals.items()
    ]


def compute_sector_exposure(total_market_value: float) -> list[SectorExposure]:
    """Every position is reported under a single "Unknown" bucket — Portfolio
    does not own sector classification (Docs/DOMAIN_OWNERSHIP.md assigns
    that to Research's "Fundamental Data"/"Industry Data"), and the Research
    domain isn't built until PROMPT.md Phase 16. An honest single bucket,
    not a fabricated per-position mapping."""
    if total_market_value <= 0:
        return []
    return [
        SectorExposure(
            sector=_UNKNOWN_SECTOR,
            market_value=round(total_market_value, _MONEY_DECIMALS),
            weight_percent=100.0,
        )
    ]


def compute_cross_account_exposure(positions: list[Position]) -> list[SymbolExposure]:
    """PROMPT.md Phase 13 implement item 3: the same symbol held in more
    than one account, aggregated. Symbols held in only one account are not
    "exposure" in the cross-account sense and are omitted here."""
    by_symbol: dict[str, list[Position]] = {}
    for p in positions:
        by_symbol.setdefault(p.symbol, []).append(p)
    result = []
    for symbol, group in sorted(by_symbol.items()):
        account_ids = sorted({p.account_id for p in group})
        if len(account_ids) < 2:
            continue
        result.append(
            SymbolExposure(
                symbol=symbol,
                total_quantity=sum(p.quantity for p in group),
                total_market_value=round(
                    sum(p.market_value or 0.0 for p in group), _MONEY_DECIMALS
                ),
                account_ids=account_ids,
            )
        )
    return result


def compute_concentration_warnings(
    weights: list[PositionWeight],
    threshold_percent: float = _DEFAULT_CONCENTRATION_THRESHOLD_PERCENT,
) -> list[ConcentrationWarning]:
    return [
        ConcentrationWarning(
            symbol=w.symbol, weight_percent=w.weight_percent, threshold_percent=threshold_percent
        )
        for w in weights
        if w.weight_percent > threshold_percent
    ]


def compute_gain_loss(positions: list[Position]) -> tuple[list[PositionGainLoss], float | None]:
    """`cost_basis` stays `None` when Schwab never reported `average_price`
    for this position — never estimated to "fill in" a gain/loss figure
    (PROMPT.md Phase 13 verification 4)."""
    results = []
    total: float | None = None
    for p in positions:
        cost_basis = (
            round(p.average_price * p.quantity, _MONEY_DECIMALS)
            if p.average_price is not None
            else None
        )
        gain_dollar = (
            round(p.market_value - cost_basis, _MONEY_DECIMALS)
            if cost_basis is not None and p.market_value is not None
            else None
        )
        gain_percent = (
            round(gain_dollar / cost_basis * 100, _PERCENT_DECIMALS)
            if gain_dollar is not None and cost_basis
            else None
        )
        results.append(
            PositionGainLoss(
                symbol=p.symbol,
                account_id=p.account_id,
                quantity=p.quantity,
                cost_basis=cost_basis,
                market_value=p.market_value,
                unrealized_gain_loss_dollar=gain_dollar,
                unrealized_gain_loss_percent=gain_percent,
            )
        )
        if gain_dollar is not None:
            total = (total or 0.0) + gain_dollar
    if total is not None:
        total = round(total, _MONEY_DECIMALS)
    return results, total


def is_snapshot_stale(taken_at: datetime, now: datetime) -> bool:
    """PROMPT.md Phase 13 verification 5: "dashboard clearly shows last
    verified sync time" — data older than `_STALENESS_THRESHOLD` is flagged,
    not silently presented as current."""
    return now - taken_at > _STALENESS_THRESHOLD


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_oauth_state(user_id: str, nonce: str, now: datetime, secret: str) -> str:
    payload = f"{user_id}:{nonce}:{now.timestamp()}"
    signature = _sign(payload, secret)
    token = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")


def verify_oauth_state(
    state: str, secret: str, now: datetime, max_age: timedelta = timedelta(minutes=10)
) -> str:
    try:
        decoded = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
        user_id, nonce, timestamp_str, signature = decoded.rsplit(":", 3)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SchwabOAuthStateInvalidError("malformed OAuth state") from exc

    payload = f"{user_id}:{nonce}:{timestamp_str}"
    expected = _sign(payload, secret)
    if not hmac.compare_digest(signature, expected):
        raise SchwabOAuthStateInvalidError("OAuth state signature mismatch")

    try:
        issued_at = datetime.fromtimestamp(float(timestamp_str), tz=UTC)
    except ValueError as exc:
        raise SchwabOAuthStateInvalidError("malformed OAuth state timestamp") from exc
    if now - issued_at > max_age:
        raise SchwabOAuthStateInvalidError("OAuth state expired")

    return user_id


def extract_code_from_redirect(pasted_value: str) -> str:
    """Schwab's fixed callback (https://127.0.0.1:8182) is never actually
    reachable — the user's browser lands on a dead page after consent and
    copies the resulting URL out of the address bar by hand. Accepts either
    that full URL or just the bare `code` value already extracted. A URL
    that doesn't contain a `code` (e.g. the user denied consent, so it's
    `?error=access_denied` instead) is a real failure, not passed through
    silently."""
    if not pasted_value.startswith("http"):
        return pasted_value
    query = parse_qs(urlsplit(pasted_value).query)
    codes = query.get("code")
    if not codes:
        raise SchwabRedirectValueInvalidError(
            "no 'code' parameter found in the pasted redirect URL"
        )
    return codes[0]


def validate_ips_rules(
    allocation_ranges: list[AllocationRange],
    restricted_securities: list[RestrictedSecurity],
) -> None:
    """PROMPT.md Phase 14 implement item 2 ("IPS editor"): the write-time
    validation an editor needs. `ConcentrationRule.max_position_percent`'s
    own `gt=0, le=100` constraint (schemas.py) already rules out a malformed
    concentration rule at the type level, so there's nothing further to
    check for it here."""
    for rule in allocation_ranges:
        if rule.min_percent > rule.max_percent:
            raise IPSValidationError(
                f"{rule.asset_type.value} allocation range has min_percent "
                f"({rule.min_percent}) greater than max_percent ({rule.max_percent})"
            )
    seen_types = [r.asset_type for r in allocation_ranges]
    if len(seen_types) != len(set(seen_types)):
        raise IPSValidationError(
            "allocation_ranges has more than one range for the same asset type"
        )

    symbols = [r.symbol.strip().upper() for r in restricted_securities]
    if any(not s for s in symbols):
        raise IPSValidationError("restricted_securities contains an empty symbol")
    if len(symbols) != len(set(symbols)):
        raise IPSValidationError("restricted_securities lists the same symbol more than once")


def evaluate_compliance(
    ips: IPSVersion, positions: list[Position], balances: list[AccountBalance]
) -> list[ComplianceBreach]:
    """PROMPT.md Phase 14 implement items 6-8: allocation ranges,
    concentration rules, and restricted securities, evaluated deterministically
    against the given positions/balances (verification 1) — no I/O, no
    randomness, no model call. Scoped to `ips.account_ids` when non-empty,
    matching PROMPT.md Phase 14 implement item 4 ("account assignment");
    otherwise evaluated across every account, mirroring
    `domains.portfolio.policies.build_snapshot`'s own total calculation so
    the two stay consistent with each other."""
    account_ids = set(ips.account_ids) if ips.account_ids else None
    scoped_positions = [p for p in positions if account_ids is None or p.account_id in account_ids]
    scoped_balances = [b for b in balances if account_ids is None or b.account_id in account_ids]
    scoped_total = sum(b.cash_balance or 0.0 for b in scoped_balances) + sum(
        p.market_value or 0.0 for p in scoped_positions
    )

    breaches: list[ComplianceBreach] = []

    totals_by_type: dict[AssetType, float] = {}
    for p in scoped_positions:
        if p.market_value is None:
            continue
        totals_by_type[p.asset_type] = totals_by_type.get(p.asset_type, 0.0) + p.market_value
    for rule in ips.allocation_ranges:
        actual_value = totals_by_type.get(rule.asset_type, 0.0)
        actual_percent = (
            round(actual_value / scoped_total * 100, _PERCENT_DECIMALS) if scoped_total else 0.0
        )
        if actual_percent < rule.min_percent or actual_percent > rule.max_percent:
            breaches.append(
                ComplianceBreach(
                    rule_type="allocation_range",
                    description=(
                        f"{rule.asset_type.value} allocation is {actual_percent}%, "
                        f"outside the IPS range [{rule.min_percent}%, {rule.max_percent}%]"
                    ),
                    detail={
                        "asset_type": rule.asset_type.value,
                        "actual_percent": actual_percent,
                        "min_percent": rule.min_percent,
                        "max_percent": rule.max_percent,
                    },
                )
            )

    for p in scoped_positions:
        if p.market_value is None or not scoped_total:
            continue
        weight_percent = round(p.market_value / scoped_total * 100, _PERCENT_DECIMALS)
        if weight_percent > ips.concentration_rule.max_position_percent:
            breaches.append(
                ComplianceBreach(
                    rule_type="concentration",
                    description=(
                        f"{p.symbol} is {weight_percent}% of tracked value, exceeding the "
                        f"IPS limit of {ips.concentration_rule.max_position_percent}%"
                    ),
                    detail={
                        "symbol": p.symbol,
                        "account_id": p.account_id,
                        "weight_percent": weight_percent,
                        "limit_percent": ips.concentration_rule.max_position_percent,
                    },
                )
            )

    restricted_symbols = {r.symbol for r in ips.restricted_securities}
    for p in scoped_positions:
        if p.symbol in restricted_symbols:
            breaches.append(
                ComplianceBreach(
                    rule_type="restricted_security",
                    description=f"{p.symbol} is held but restricted by the IPS",
                    detail={"symbol": p.symbol, "account_id": p.account_id},
                )
            )

    return breaches
