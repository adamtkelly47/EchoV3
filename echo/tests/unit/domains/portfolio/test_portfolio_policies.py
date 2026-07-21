from datetime import UTC, datetime, timedelta

import pytest

from domains.portfolio.errors import (
    IPSValidationError,
    SchwabOAuthStateInvalidError,
    SchwabRedirectValueInvalidError,
)
from domains.portfolio.models import AssetType
from domains.portfolio.policies import (
    build_snapshot,
    compute_asset_class_exposure,
    compute_concentration_warnings,
    compute_cross_account_exposure,
    compute_gain_loss,
    compute_position_weights,
    compute_sector_exposure,
    evaluate_compliance,
    extract_code_from_redirect,
    generate_oauth_state,
    is_refresh_token_expired,
    is_snapshot_stale,
    mask_account_number,
    needs_refresh,
    parse_account,
    parse_balance,
    parse_positions,
    parse_price_history,
    parse_quote,
    reconcile,
    validate_ips_rules,
    verify_oauth_state,
)
from domains.portfolio.schemas import (
    AccountBalance,
    AllocationRange,
    ConcentrationRule,
    IPSVersion,
    Position,
    RestrictedSecurity,
    SchwabCredential,
)


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


def _position(**overrides: object) -> Position:
    defaults: dict[str, object] = {
        "account_id": "account_1",
        "user_id": "user_1",
        "symbol": "AAPL",
        "asset_type": AssetType.EQUITY,
        "quantity": 100.0,
        "market_value": 18500.0,
        "average_price": 150.0,
        "source_record_id": "s",
        "synced_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Position(**defaults)  # type: ignore[arg-type]


def test_compute_position_weights_sums_to_one_hundred_percent() -> None:
    positions = [
        _position(symbol="AAPL", market_value=7500.0),
        _position(symbol="MSFT", market_value=2500.0),
    ]
    weights = compute_position_weights(positions, total_market_value=10000.0)
    assert weights[0].weight_percent == 75.0
    assert weights[1].weight_percent == 25.0


def test_compute_position_weights_excludes_missing_market_value() -> None:
    positions = [_position(symbol="AAPL", market_value=None)]
    weights = compute_position_weights(positions, total_market_value=10000.0)
    assert weights == []


def test_compute_asset_class_exposure_groups_by_type() -> None:
    positions = [
        _position(symbol="AAPL", asset_type=AssetType.EQUITY, market_value=6000.0),
        _position(symbol="SCHF", asset_type=AssetType.ETF, market_value=4000.0),
    ]
    exposure = compute_asset_class_exposure(positions, total_market_value=10000.0)
    by_type = {e.asset_type: e.weight_percent for e in exposure}
    assert by_type[AssetType.EQUITY] == 60.0
    assert by_type[AssetType.ETF] == 40.0


def test_compute_sector_exposure_is_a_single_unknown_bucket() -> None:
    """No real sector data source exists until the Research domain
    (PROMPT.md Phase 16+) — this must never fabricate a per-position
    mapping (Docs/DECISION_LOG.md's Phase 13 entry)."""
    exposure = compute_sector_exposure(total_market_value=10000.0)
    assert len(exposure) == 1
    assert exposure[0].sector == "Unknown"
    assert exposure[0].weight_percent == 100.0


def test_compute_cross_account_exposure_only_includes_multi_account_symbols() -> None:
    positions = [
        _position(symbol="AAPL", account_id="account_1", quantity=100.0, market_value=18500.0),
        _position(symbol="AAPL", account_id="account_2", quantity=50.0, market_value=9250.0),
        _position(symbol="MSFT", account_id="account_1", quantity=10.0, market_value=3000.0),
    ]
    exposure = compute_cross_account_exposure(positions)
    assert len(exposure) == 1
    assert exposure[0].symbol == "AAPL"
    assert exposure[0].total_quantity == 150.0
    assert exposure[0].total_market_value == 27750.0
    assert exposure[0].account_ids == ["account_1", "account_2"]


def test_compute_concentration_warnings_flags_positions_over_threshold() -> None:
    positions = [
        _position(symbol="AAPL", market_value=9000.0),
        _position(symbol="MSFT", market_value=1000.0),
    ]
    weights = compute_position_weights(positions, total_market_value=10000.0)
    warnings = compute_concentration_warnings(weights, threshold_percent=10.0)
    assert len(warnings) == 1
    assert warnings[0].symbol == "AAPL"
    assert warnings[0].weight_percent == 90.0


def test_compute_gain_loss_computes_from_average_price() -> None:
    positions = [_position(quantity=100.0, average_price=150.0, market_value=18500.0)]
    results, total = compute_gain_loss(positions)
    assert results[0].cost_basis == 15000.0
    assert results[0].unrealized_gain_loss_dollar == 3500.0
    assert total == 3500.0


def test_compute_gain_loss_missing_average_price_stays_none_not_estimated() -> None:
    positions = [_position(average_price=None, market_value=18500.0)]
    results, total = compute_gain_loss(positions)
    assert results[0].cost_basis is None
    assert results[0].unrealized_gain_loss_dollar is None
    assert total is None


def test_is_snapshot_stale_flags_data_older_than_24_hours() -> None:
    taken_at = datetime(2026, 1, 1, tzinfo=UTC)
    assert not is_snapshot_stale(taken_at, taken_at + timedelta(hours=1))
    assert is_snapshot_stale(taken_at, taken_at + timedelta(hours=25))


def test_validate_ips_rules_rejects_min_greater_than_max() -> None:
    with pytest.raises(IPSValidationError):
        validate_ips_rules(
            [AllocationRange(asset_type=AssetType.EQUITY, min_percent=80.0, max_percent=50.0)], []
        )


def test_validate_ips_rules_rejects_duplicate_asset_type() -> None:
    with pytest.raises(IPSValidationError):
        validate_ips_rules(
            [
                AllocationRange(asset_type=AssetType.EQUITY, min_percent=0.0, max_percent=50.0),
                AllocationRange(asset_type=AssetType.EQUITY, min_percent=0.0, max_percent=80.0),
            ],
            [],
        )


def test_validate_ips_rules_rejects_duplicate_restricted_symbol() -> None:
    with pytest.raises(IPSValidationError):
        validate_ips_rules(
            [], [RestrictedSecurity(symbol="TSLA"), RestrictedSecurity(symbol="tsla")]
        )


def test_validate_ips_rules_accepts_well_formed_rules() -> None:
    validate_ips_rules(
        [AllocationRange(asset_type=AssetType.EQUITY, min_percent=40.0, max_percent=80.0)],
        [RestrictedSecurity(symbol="XYZ")],
    )  # no raise


def _ips(**overrides: object) -> IPSVersion:
    defaults: dict[str, object] = {
        "ips_id": "ips_1",
        "version_number": 1,
        "user_id": "user_1",
        "account_ids": [],
        "allocation_ranges": [],
        "concentration_rule": ConcentrationRule(max_position_percent=25.0),
        "restricted_securities": [],
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "is_active": True,
    }
    defaults.update(overrides)
    return IPSVersion(**defaults)  # type: ignore[arg-type]


def test_evaluate_compliance_flags_allocation_range_breach() -> None:
    ips = _ips(
        allocation_ranges=[
            AllocationRange(asset_type=AssetType.EQUITY, min_percent=0.0, max_percent=50.0)
        ]
    )
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=100,
            market_value=8000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    balances = [
        AccountBalance(
            account_id="a1",
            user_id="u1",
            cash_balance=2000.0,
            schwab_reported_total=10000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    breaches = evaluate_compliance(ips, positions, balances)
    assert any(b.rule_type == "allocation_range" for b in breaches)


def test_evaluate_compliance_flags_concentration_breach() -> None:
    ips = _ips(concentration_rule=ConcentrationRule(max_position_percent=10.0))
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=100,
            market_value=9000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    balances = [
        AccountBalance(
            account_id="a1",
            user_id="u1",
            cash_balance=1000.0,
            schwab_reported_total=10000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    breaches = evaluate_compliance(ips, positions, balances)
    concentration_breaches = [b for b in breaches if b.rule_type == "concentration"]
    assert len(concentration_breaches) == 1
    assert concentration_breaches[0].detail["symbol"] == "AAPL"


def test_evaluate_compliance_flags_restricted_security() -> None:
    ips = _ips(restricted_securities=[RestrictedSecurity(symbol="TSLA")])
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="TSLA",
            asset_type=AssetType.EQUITY,
            quantity=10,
            market_value=2500.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    breaches = evaluate_compliance(ips, positions, [])
    assert any(
        b.rule_type == "restricted_security" and b.detail["symbol"] == "TSLA" for b in breaches
    )


def test_evaluate_compliance_no_breaches_when_within_all_rules() -> None:
    ips = _ips(
        allocation_ranges=[
            AllocationRange(asset_type=AssetType.EQUITY, min_percent=0.0, max_percent=100.0)
        ],
        concentration_rule=ConcentrationRule(max_position_percent=100.0),
    )
    positions = [
        Position(
            account_id="a1",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=10,
            market_value=1000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    assert evaluate_compliance(ips, positions, []) == []


def test_evaluate_compliance_scopes_to_ips_account_ids() -> None:
    """PROMPT.md Phase 14 implement item 4 ("account assignment"): a
    position in an account the IPS doesn't apply to must never be
    evaluated against it."""
    ips = _ips(
        account_ids=["account_scoped"],
        concentration_rule=ConcentrationRule(max_position_percent=10.0),
    )
    positions = [
        Position(
            account_id="account_other",
            user_id="u1",
            symbol="AAPL",
            asset_type=AssetType.EQUITY,
            quantity=100,
            market_value=9000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    balances = [
        AccountBalance(
            account_id="account_other",
            user_id="u1",
            cash_balance=1000.0,
            schwab_reported_total=10000.0,
            source_record_id="s",
            synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    assert evaluate_compliance(ips, positions, balances) == []
