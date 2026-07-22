from datetime import UTC, datetime

from domains.research.policies import (
    compute_insider_cluster_feature,
    compute_insider_profile,
    compute_ownership_change_percent,
    compute_size_anomaly,
    compute_transaction_value,
    normalize_transaction_type,
    parse_form4_transactions,
)
from domains.research.schemas import InsiderTransaction, TransactionType


def test_normalize_transaction_type_maps_known_codes() -> None:
    assert normalize_transaction_type("P") == TransactionType.OPEN_MARKET_PURCHASE
    assert normalize_transaction_type("S") == TransactionType.OPEN_MARKET_SALE
    assert normalize_transaction_type("A") == TransactionType.GRANT_AWARD
    assert normalize_transaction_type("M") == TransactionType.OPTION_EXERCISE
    assert normalize_transaction_type("X") == TransactionType.OPTION_EXERCISE
    assert normalize_transaction_type("F") == TransactionType.TAX_WITHHOLDING
    assert normalize_transaction_type("G") == TransactionType.GIFT


def test_normalize_transaction_type_unknown_code_is_other() -> None:
    assert normalize_transaction_type("Z") == TransactionType.OTHER


def _raw_filing(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "reporting_owner_cik": "0001234567",
        "reporting_owner_name": "Jane Insider",
        "is_director": True,
        "is_officer": False,
        "is_ten_percent_owner": False,
        "officer_title": None,
        "aff10b5_one": False,
        "transactions": [
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "S",
                "shares": "800",
                "price_per_share": "355.00",
                "acquired_disposed": "D",
                "shares_owned_following": "5000",
                "footnote_ids": [],
            }
        ],
        "footnotes": {},
    }
    defaults.update(overrides)
    return defaults


def test_parse_form4_transactions_distinguishes_grant_from_open_market_purchase() -> None:
    """PROMPT.md Phase 18 verification 1."""
    grant_raw = _raw_filing(
        transactions=[
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "A",
                "shares": "100",
                "price_per_share": None,
                "acquired_disposed": "A",
                "shares_owned_following": "5100",
                "footnote_ids": [],
            }
        ]
    )
    purchase_raw = _raw_filing(
        transactions=[
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "P",
                "shares": "100",
                "price_per_share": "50.00",
                "acquired_disposed": "A",
                "shares_owned_following": "5100",
                "footnote_ids": [],
            }
        ]
    )
    grant = parse_form4_transactions(
        grant_raw,
        issuer_id="issuer_1",
        accession_number="acc1",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    purchase = parse_form4_transactions(
        purchase_raw,
        issuer_id="issuer_1",
        accession_number="acc2",
        source_record_id="s2",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert grant[0].transaction_type == TransactionType.GRANT_AWARD
    assert purchase[0].transaction_type == TransactionType.OPEN_MARKET_PURCHASE


def test_parse_form4_transactions_flags_planned_sale_only_when_aff10b5_one_true() -> None:
    """PROMPT.md Phase 18 verification 2: planned sales are only identified
    when the filing's own data supports it."""
    planned_raw = _raw_filing(aff10b5_one=True)
    unplanned_raw = _raw_filing(aff10b5_one=False)
    planned = parse_form4_transactions(
        planned_raw,
        issuer_id="issuer_1",
        accession_number="acc1",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    unplanned = parse_form4_transactions(
        unplanned_raw,
        issuer_id="issuer_1",
        accession_number="acc2",
        source_record_id="s2",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert planned[0].is_planned_sale is True
    assert unplanned[0].is_planned_sale is False


def test_parse_form4_transactions_never_flags_planned_sale_for_a_purchase() -> None:
    raw = _raw_filing(
        aff10b5_one=True,
        transactions=[
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "P",
                "shares": "100",
                "price_per_share": "50.00",
                "acquired_disposed": "A",
                "shares_owned_following": "5100",
                "footnote_ids": [],
            }
        ],
    )
    transactions = parse_form4_transactions(
        raw,
        issuer_id="issuer_1",
        accession_number="acc1",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert transactions[0].is_planned_sale is False


def test_parse_form4_transactions_skips_transaction_missing_required_field() -> None:
    raw = _raw_filing(
        transactions=[
            {
                "transaction_date": None,  # missing date -> skipped
                "transaction_code": "S",
                "shares": "800",
                "price_per_share": "355.00",
                "acquired_disposed": "D",
                "shares_owned_following": "5000",
                "footnote_ids": [],
            }
        ]
    )
    transactions = parse_form4_transactions(
        raw,
        issuer_id="issuer_1",
        accession_number="acc1",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert transactions == []


def test_parse_form4_transactions_returns_empty_when_no_reporting_owner() -> None:
    raw = _raw_filing(reporting_owner_cik=None)
    transactions = parse_form4_transactions(
        raw,
        issuer_id="issuer_1",
        accession_number="acc1",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert transactions == []


def test_parse_form4_transactions_is_idempotent_across_reingestion() -> None:
    """Re-ingesting the same accession (any scheduled re-sync will do this,
    since the provider always returns the most recent N filings) must
    resolve to the same transaction_id per transaction, not a fresh random
    one — otherwise `save_insider_transactions`'s upsert-by-transaction_id
    would create duplicate rows and silently corrupt every anomaly baseline
    and profile total that reads the full history back. Caught live against
    real UNH filings (Docs/DECISION_LOG.md's Phase 18 entry)."""
    raw = _raw_filing()
    first = parse_form4_transactions(
        raw,
        issuer_id="issuer_1",
        accession_number="0000731766-26-000123",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    second = parse_form4_transactions(
        raw,
        issuer_id="issuer_1",
        accession_number="0000731766-26-000123",
        source_record_id="s2",
        now=datetime(2026, 1, 21, tzinfo=UTC),
    )
    assert first[0].transaction_id == second[0].transaction_id


def test_parse_form4_transactions_concatenates_footnotes_by_id() -> None:
    raw = _raw_filing(
        footnotes={"F1": "Represents a gift to a family trust.", "F2": "Unrelated footnote."},
        transactions=[
            {
                "transaction_date": "2026-01-15",
                "transaction_code": "G",
                "shares": "50",
                "price_per_share": None,
                "acquired_disposed": "D",
                "shares_owned_following": "4950",
                "footnote_ids": ["F1"],
            }
        ],
    )
    transactions = parse_form4_transactions(
        raw,
        issuer_id="issuer_1",
        accession_number="acc1",
        source_record_id="s1",
        now=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert transactions[0].footnote_text == "Represents a gift to a family trust."


def test_compute_transaction_value_none_when_no_price_reported() -> None:
    """PROMPT.md Phase 18 verification 3 / Docs/DATA_MODEL.md: missing stays
    missing — a stock grant with no reported price is never estimated."""
    assert compute_transaction_value(100.0, None) is None


def test_compute_transaction_value_multiplies_shares_by_price() -> None:
    assert compute_transaction_value(800.0, 355.0) == 284000.0


def test_compute_ownership_change_percent_none_when_no_post_transaction_balance() -> None:
    assert compute_ownership_change_percent(100.0, None, "A") is None


def test_compute_ownership_change_percent_computes_from_real_filing_numbers() -> None:
    """PROMPT.md Phase 18 verification 3: ownership changes computed in
    code from the filing's own post-transaction balance."""
    # Acquired 100 shares, now owns 1100 -> owned 1000 before -> 10% change.
    percent = compute_ownership_change_percent(100.0, 1100.0, "A")
    assert percent == 10.0


def test_compute_ownership_change_percent_disposed_direction() -> None:
    # Disposed 100 shares, now owns 900 -> owned 1000 before -> 10% change.
    percent = compute_ownership_change_percent(100.0, 900.0, "D")
    assert percent == 10.0


def _txn(**overrides: object) -> InsiderTransaction:
    defaults: dict[str, object] = {
        "issuer_id": "issuer_1",
        "insider_cik": "0001234567",
        "insider_name": "Jane Insider",
        "is_director": True,
        "is_officer": False,
        "is_ten_percent_owner": False,
        "transaction_date": datetime(2026, 1, 15, tzinfo=UTC),
        "transaction_code": "S",
        "transaction_type": TransactionType.OPEN_MARKET_SALE,
        "shares": 100.0,
        "acquired_disposed": "D",
        "filing_accession_number": "acc1",
        "source_record_id": "s1",
        "synced_at": datetime(2026, 1, 20, tzinfo=UTC),
    }
    defaults.update(overrides)
    return InsiderTransaction(**defaults)  # type: ignore[arg-type]


def test_compute_size_anomaly_requires_at_least_two_prior_transactions() -> None:
    """PROMPT.md Phase 18 verification 4: with too little history, no
    fabricated feature is produced."""
    latest = _txn(shares=1000.0, transaction_date=datetime(2026, 3, 1, tzinfo=UTC))
    one_prior = [_txn(shares=100.0, transaction_date=datetime(2026, 1, 1, tzinfo=UTC)), latest]
    assert compute_size_anomaly(latest, one_prior) is None


def test_compute_size_anomaly_states_the_comparison_baseline() -> None:
    """PROMPT.md Phase 18 verification 4: anomaly claims explain the
    comparison baseline explicitly, never a bare score."""
    latest = _txn(shares=1000.0, transaction_date=datetime(2026, 3, 1, tzinfo=UTC))
    history = [
        _txn(shares=100.0, transaction_date=datetime(2026, 1, 1, tzinfo=UTC)),
        _txn(shares=100.0, transaction_date=datetime(2026, 2, 1, tzinfo=UTC)),
        latest,
    ]
    feature = compute_size_anomaly(latest, history)
    assert feature is not None
    assert feature.value == 10.0  # 1000 / average(100, 100)
    assert "own average transaction size" in feature.baseline_description
    assert "2 prior recorded" in feature.baseline_description
    assert feature.is_notable is True


def test_compute_size_anomaly_not_notable_below_threshold() -> None:
    latest = _txn(shares=150.0, transaction_date=datetime(2026, 3, 1, tzinfo=UTC))
    history = [
        _txn(shares=100.0, transaction_date=datetime(2026, 1, 1, tzinfo=UTC)),
        _txn(shares=100.0, transaction_date=datetime(2026, 2, 1, tzinfo=UTC)),
        latest,
    ]
    feature = compute_size_anomaly(latest, history)
    assert feature is not None
    assert feature.is_notable is False


def test_compute_insider_cluster_feature_counts_distinct_insiders_in_window() -> None:
    """PROMPT.md Phase 18 verification 4: cluster features state their
    window and comparison set explicitly."""
    target = _txn(
        insider_cik="cik1", acquired_disposed="D", transaction_date=datetime(2026, 3, 1, tzinfo=UTC)
    )
    same_week_other_insider = _txn(
        insider_cik="cik2", acquired_disposed="D", transaction_date=datetime(2026, 3, 3, tzinfo=UTC)
    )
    outside_window = _txn(
        insider_cik="cik3", acquired_disposed="D", transaction_date=datetime(2026, 4, 1, tzinfo=UTC)
    )
    different_direction = _txn(
        insider_cik="cik4", acquired_disposed="A", transaction_date=datetime(2026, 3, 2, tzinfo=UTC)
    )
    feature = compute_insider_cluster_feature(
        target, [target, same_week_other_insider, outside_window, different_direction]
    )
    assert feature is not None
    assert feature.value == 2.0  # cik1 (self) + cik2
    assert "within 7 days" in feature.baseline_description


def test_compute_insider_profile_none_for_no_transactions() -> None:
    assert compute_insider_profile("cik1", "Jane Insider", "issuer_1", []) is None


def test_compute_insider_profile_sums_purchases_and_sales_separately() -> None:
    purchase = _txn(
        transaction_type=TransactionType.OPEN_MARKET_PURCHASE,
        shares=100.0,
        transaction_value=5000.0,
        transaction_date=datetime(2026, 1, 1, tzinfo=UTC),
    )
    sale = _txn(
        transaction_type=TransactionType.OPEN_MARKET_SALE,
        shares=50.0,
        transaction_value=2500.0,
        transaction_date=datetime(2026, 2, 1, tzinfo=UTC),
    )
    profile = compute_insider_profile("cik1", "Jane Insider", "issuer_1", [purchase, sale])
    assert profile is not None
    assert profile.total_purchased_value == 5000.0
    assert profile.total_sold_value == 2500.0
    assert profile.transaction_count == 2
    assert profile.average_transaction_shares == 75.0
    assert profile.first_transaction_date == datetime(2026, 1, 1, tzinfo=UTC)
    assert profile.last_transaction_date == datetime(2026, 2, 1, tzinfo=UTC)
