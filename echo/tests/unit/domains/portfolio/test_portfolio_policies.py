from datetime import UTC, datetime, timedelta

import pytest

from domains.portfolio.errors import SchwabOAuthStateInvalidError, SchwabRedirectValueInvalidError
from domains.portfolio.models import AssetType
from domains.portfolio.policies import (
    build_snapshot,
    extract_code_from_redirect,
    generate_oauth_state,
    is_refresh_token_expired,
    mask_account_number,
    needs_refresh,
    parse_account,
    parse_balance,
    parse_positions,
    parse_price_history,
    parse_quote,
    reconcile,
    verify_oauth_state,
)
from domains.portfolio.schemas import AccountBalance, Position, SchwabCredential


def _credential(**overrides: object) -> SchwabCredential:
    defaults: dict[str, object] = {
        "user_id": "user_1",
        "encrypted_access_token": "enc-access",
        "encrypted_refresh_token": "enc-refresh",
        "access_token_expires_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "refresh_token_expires_at": datetime(2026, 1, 8, tzinfo=UTC),
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SchwabCredential(**defaults)  # type: ignore[arg-type]


def test_mask_account_number_keeps_only_last_four() -> None:
    assert mask_account_number("12345678") == "••••5678"
    assert mask_account_number("123") == "••••123"  # still masked, just short


def test_needs_refresh_true_within_buffer() -> None:
    credential = _credential(access_token_expires_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    assert not needs_refresh(credential, datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC))
    assert needs_refresh(credential, datetime(2026, 1, 1, 11, 56, 0, tzinfo=UTC))


def test_is_refresh_token_expired() -> None:
    credential = _credential(refresh_token_expires_at=datetime(2026, 1, 8, tzinfo=UTC))
    assert not is_refresh_token_expired(credential, datetime(2026, 1, 7, tzinfo=UTC))
    assert is_refresh_token_expired(credential, datetime(2026, 1, 8, 0, 0, 1, tzinfo=UTC))


def test_parse_account_masks_real_number_and_keeps_type() -> None:
    raw = {"securitiesAccount": {"type": "INDIVIDUAL", "accountNumber": "87654321"}}
    account = parse_account(
        raw, user_id="user_1", account_hash="hash-abc", synced_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert account.display_mask == "••••4321"
    assert account.account_type == "INDIVIDUAL"
    assert account.account_hash == "hash-abc"


def test_parse_balance() -> None:
    raw = {
        "securitiesAccount": {
            "currentBalances": {"cashBalance": 5000.0, "liquidationValue": 55000.0}
        }
    }
    balance = parse_balance(
        raw,
        account_id="account_1",
        user_id="user_1",
        source_record_id="source_1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert balance.cash_balance == 5000.0
    assert balance.schwab_reported_total == 55000.0


def test_parse_positions_computes_net_quantity_and_missing_stays_missing() -> None:
    raw = {
        "securitiesAccount": {
            "positions": [
                {
                    "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                    "longQuantity": 100,
                    "shortQuantity": 0,
                    "marketValue": 18500.0,
                    "averagePrice": 175.0,
                },
                {
                    "instrument": {"symbol": "MMF", "assetType": "CASH_EQUIVALENT"},
                    "longQuantity": 1000,
                    "shortQuantity": 0,
                    # no marketValue/averagePrice at all
                },
            ]
        }
    }
    positions = parse_positions(
        raw,
        account_id="account_1",
        user_id="user_1",
        source_record_id="source_1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert positions[0].symbol == "AAPL"
    assert positions[0].asset_type == AssetType.EQUITY
    assert positions[0].quantity == 100
    assert positions[0].market_value == 18500.0
    assert positions[1].symbol == "MMF"
    assert positions[1].market_value is None  # missing, not estimated
    assert positions[1].average_price is None


def test_parse_positions_classifies_etf_via_instrument_type_not_broad_asset_type() -> None:
    """Live-verified (Docs/DECISION_LOG.md's Phase 12 entry): Schwab reports
    an ETF's `assetType` as the broad "COLLECTIVE_INVESTMENT" bucket — the
    actual ETF classification is in the more specific `instrument.type`
    field, which must be checked first."""
    raw = {
        "securitiesAccount": {
            "positions": [
                {
                    "instrument": {
                        "symbol": "SCHF",
                        "assetType": "COLLECTIVE_INVESTMENT",
                        "type": "EXCHANGE_TRADED_FUND",
                    },
                    "longQuantity": 14.0846,
                    "shortQuantity": 0,
                    "marketValue": 385.0,
                }
            ]
        }
    }
    positions = parse_positions(
        raw,
        account_id="account_1",
        user_id="user_1",
        source_record_id="s",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert positions[0].asset_type == AssetType.ETF


def test_parse_positions_nets_short_quantity() -> None:
    raw = {
        "securitiesAccount": {
            "positions": [
                {
                    "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                    "longQuantity": 0,
                    "shortQuantity": 50,
                }
            ]
        }
    }
    positions = parse_positions(
        raw,
        account_id="account_1",
        user_id="user_1",
        source_record_id="s",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert positions[0].quantity == -50


def test_parse_quote() -> None:
    raw = {"quote": {"lastPrice": 185.5, "netChange": 1.5, "netPercentChange": 0.82}}
    quote = parse_quote(
        raw,
        symbol="AAPL",
        source_record_id="source_1",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert quote.price == 185.5
    assert quote.change_dollar == 1.5
    assert quote.change_percent == 0.82


def test_parse_price_history() -> None:
    raw = {
        "candles": [
            {
                "datetime": 1767225600000,
                "open": 100,
                "high": 105,
                "low": 99,
                "close": 104,
                "volume": 1000,
            }
        ]
    }
    points = parse_price_history(raw)
    assert len(points) == 1
    assert points[0].close == 104
    assert points[0].volume == 1000


def test_reconcile_matches_within_tolerance() -> None:
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=100,
            market_value=18500.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    balance = AccountBalance(
        account_id="a1",
        user_id="u1",
        cash_balance=5000.0,
        schwab_reported_total=23500.0,
        source_record_id="s",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    reconciled, diff, warnings = reconcile(positions, balance)
    assert reconciled is True
    assert diff == 0.0
    assert warnings == []


def test_reconcile_flags_real_mismatch() -> None:
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=100,
            market_value=18500.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    balance = AccountBalance(
        account_id="a1",
        user_id="u1",
        cash_balance=5000.0,
        schwab_reported_total=99999.0,  # deliberately wrong
        source_record_id="s",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    reconciled, diff, warnings = reconcile(positions, balance)
    assert reconciled is False
    assert diff is not None and abs(diff) > 0.01
    assert any("mismatch" in w for w in warnings)


def test_reconcile_missing_market_value_produces_warning_not_estimate() -> None:
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=100,
            market_value=None,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    balance = AccountBalance(
        account_id="a1",
        user_id="u1",
        cash_balance=5000.0,
        schwab_reported_total=5000.0,
        source_record_id="s",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    reconciled, _, warnings = reconcile(positions, balance)
    assert reconciled is True  # cash alone matches Schwab's total
    assert any("missing market_value" in w for w in warnings)


def test_build_snapshot_produces_visible_warnings_for_partial_data() -> None:
    snapshot = build_snapshot(
        "user_1",
        datetime(2026, 1, 1, tzinfo=UTC),
        ["account_1"],
        [],
        [],
        ["one account's positions call failed"],
    )
    assert snapshot.warnings == ["one account's positions call failed"]


def test_generate_and_verify_oauth_state_round_trips() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce", now, "secret")
    assert verify_oauth_state(state, "secret", now + timedelta(minutes=1)) == "user_1"


def test_verify_oauth_state_rejects_wrong_secret() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = generate_oauth_state("user_1", "nonce", now, "correct")
    with pytest.raises(SchwabOAuthStateInvalidError):
        verify_oauth_state(state, "wrong", now)


def test_extract_code_from_redirect_handles_full_url() -> None:
    url = "https://127.0.0.1:8182/?code=abc123&session=xyz"
    assert extract_code_from_redirect(url) == "abc123"


def test_extract_code_from_redirect_handles_bare_code() -> None:
    assert extract_code_from_redirect("abc123") == "abc123"


def test_extract_code_from_redirect_rejects_url_without_code() -> None:
    with pytest.raises(SchwabRedirectValueInvalidError):
        extract_code_from_redirect("https://127.0.0.1:8182/?error=access_denied")
