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

from domains.portfolio.errors import SchwabOAuthStateInvalidError, SchwabRedirectValueInvalidError
from domains.portfolio.models import AssetType
from domains.portfolio.schemas import (
    Account,
    AccountBalance,
    PortfolioSnapshot,
    Position,
    PriceHistoryPoint,
    Quote,
    SchwabCredential,
)

# A rounding-error tolerance, not a "close enough" fudge on real
# discrepancies (PROMPT.md Phase 12 verification 1: "account totals
# reconcile") — cents-level floating point noise, nothing more.
_RECONCILIATION_TOLERANCE = 0.01

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
