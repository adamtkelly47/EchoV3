from datetime import UTC, datetime

import pytest

from domains.research.policies import (
    build_committee_assignments,
    compute_bracket_size_anomaly,
    compute_committee_relationship_features,
    compute_filing_delay_days,
    compute_politician_cluster_feature,
    compute_politician_trade_profile,
    is_filing_late,
    normalize_politician_owner,
    normalize_politician_transaction_type,
    parse_ptr_amount_range,
    parse_ptr_transactions,
    resolve_politician_identity,
)
from domains.research.schemas import (
    Chamber,
    CommitteeAssignment,
    PoliticianOwner,
    PoliticianTransaction,
    PoliticianTransactionType,
)


def test_normalize_politician_transaction_type_maps_known_values() -> None:
    assert normalize_politician_transaction_type("Purchase") == PoliticianTransactionType.PURCHASE
    assert (
        normalize_politician_transaction_type("Sale (Full)") == PoliticianTransactionType.SALE_FULL
    )
    assert (
        normalize_politician_transaction_type("Sale (Partial)")
        == PoliticianTransactionType.SALE_PARTIAL
    )
    assert normalize_politician_transaction_type("Exchange") == PoliticianTransactionType.EXCHANGE


def test_normalize_politician_transaction_type_unknown_is_other() -> None:
    assert normalize_politician_transaction_type("Gift") == PoliticianTransactionType.OTHER


def test_normalize_politician_owner_maps_known_values() -> None:
    assert normalize_politician_owner("Self") == PoliticianOwner.SELF
    assert normalize_politician_owner("Joint") == PoliticianOwner.JOINT
    assert normalize_politician_owner("Spouse") == PoliticianOwner.SPOUSE
    assert normalize_politician_owner("Dependent Child") == PoliticianOwner.DEPENDENT_CHILD


def test_normalize_politician_owner_unknown_is_other() -> None:
    assert normalize_politician_owner("Trust") == PoliticianOwner.OTHER


def test_parse_ptr_amount_range_bounded() -> None:
    """PROMPT.md Phase 19 verification 1: both real boundary figures are
    returned, never collapsed into one number."""
    assert parse_ptr_amount_range("$1,001 - $15,000") == (1001.0, 15000.0)
    assert parse_ptr_amount_range("$5,000,001 - $25,000,000") == (5000001.0, 25000000.0)


def test_parse_ptr_amount_range_open_ended() -> None:
    """An "Over $X" disclosure is genuinely unbounded — the high boundary
    is None, not a fabricated ceiling."""
    assert parse_ptr_amount_range("Over $50,000,000") == (50000000.0, None)


def test_parse_ptr_amount_range_unrecognized_raises() -> None:
    with pytest.raises(ValueError, match="unrecognized"):
        parse_ptr_amount_range("N/A")


def test_compute_filing_delay_days() -> None:
    filed_at = datetime(2026, 3, 1, tzinfo=UTC)
    transaction_date = datetime(2026, 2, 1, tzinfo=UTC)
    assert compute_filing_delay_days(filed_at, transaction_date) == 28


def test_is_filing_late_uses_stock_act_45_day_deadline() -> None:
    """PROMPT.md Phase 19 implement item 6: filing delay."""
    assert is_filing_late(45) is False
    assert is_filing_late(46) is True


def _raw_ptr(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "transactions": [
            {
                "transaction_date": "03/27/2026",
                "owner": "Self",
                "ticker": "UHS",
                "asset_name": "Universal Health Services, Inc. Common Stock",
                "asset_type": "Stock",
                "transaction_type": "Purchase",
                "amount_text": "$1,001 - $15,000",
                "comment": "--",
            }
        ]
    }
    defaults.update(overrides)
    return defaults


def test_parse_ptr_transactions_extracts_expected_fields() -> None:
    raw = _raw_ptr()
    transactions = parse_ptr_transactions(
        raw,
        report_id="fda235b3",
        politician_name="Alan Armstrong",
        politician_bioguide_id="A000376",
        state="WY",
        party="Republican",
        filed_at=datetime(2026, 7, 21, tzinfo=UTC),
        source_record_id="s1",
        now=datetime(2026, 7, 21, tzinfo=UTC),
    )
    assert len(transactions) == 1
    t = transactions[0]
    assert t.ticker == "UHS"
    assert t.transaction_type == PoliticianTransactionType.PURCHASE
    assert t.owner == PoliticianOwner.SELF
    assert t.range_low == 1001.0
    assert t.range_high == 15000.0
    assert t.comment is None  # "--" normalized to None
    assert t.filing_delay_days == compute_filing_delay_days(
        datetime(2026, 7, 21, tzinfo=UTC), datetime(2026, 3, 27, tzinfo=UTC)
    )


def test_parse_ptr_transactions_is_idempotent_across_reingestion() -> None:
    """Same real-world lesson as Phase 18's Form 4 fix, applied here from
    the start: re-ingesting the same report must resolve to the same
    transaction_id, not a fresh random one."""
    raw = _raw_ptr()
    first = parse_ptr_transactions(
        raw,
        report_id="fda235b3",
        politician_name="Alan Armstrong",
        politician_bioguide_id=None,
        state=None,
        party=None,
        filed_at=datetime(2026, 7, 21, tzinfo=UTC),
        source_record_id="s1",
        now=datetime(2026, 7, 21, tzinfo=UTC),
    )
    second = parse_ptr_transactions(
        raw,
        report_id="fda235b3",
        politician_name="Alan Armstrong",
        politician_bioguide_id=None,
        state=None,
        party=None,
        filed_at=datetime(2026, 7, 21, tzinfo=UTC),
        source_record_id="s2",
        now=datetime(2026, 7, 22, tzinfo=UTC),
    )
    assert first[0].transaction_id == second[0].transaction_id


def test_parse_ptr_transactions_skips_row_with_unparseable_amount() -> None:
    raw = _raw_ptr(
        transactions=[
            {
                "transaction_date": "03/27/2026",
                "owner": "Self",
                "ticker": "UHS",
                "asset_name": "Universal Health Services, Inc. Common Stock",
                "asset_type": "Stock",
                "transaction_type": "Purchase",
                "amount_text": "N/A",
                "comment": "--",
            }
        ]
    )
    transactions = parse_ptr_transactions(
        raw,
        report_id="fda235b3",
        politician_name="Alan Armstrong",
        politician_bioguide_id=None,
        state=None,
        party=None,
        filed_at=datetime(2026, 7, 21, tzinfo=UTC),
        source_record_id="s1",
        now=datetime(2026, 7, 21, tzinfo=UTC),
    )
    assert transactions == []


def _legislator(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "id": {"bioguide": "M000355"},
        "name": {"first": "Mitch", "last": "McConnell"},
        "terms": [
            {
                "type": "sen",
                "start": "2021-01-03",
                "end": "2027-01-03",
                "state": "KY",
                "party": "Republican",
            }
        ],
    }
    defaults.update(overrides)
    return defaults


def test_resolve_politician_identity_matches_on_last_name() -> None:
    """PROMPT.md Phase 19 implement item 2. Real eFD data reports names
    like "A. Mitchell" for Mitch McConnell — normalized last-name matching
    against currently-serving senators resolves this correctly."""
    legislators = [_legislator()]
    identity = resolve_politician_identity(
        first_name="A. Mitchell",
        last_name="McConnell, Jr.",
        reference_date=datetime(2026, 6, 1, tzinfo=UTC),
        legislators=legislators,
    )
    assert identity["bioguide_id"] == "M000355"
    assert identity["state"] == "KY"
    assert identity["party"] == "Republican"


def test_resolve_politician_identity_disambiguates_by_first_name_when_ambiguous() -> None:
    legislators = [
        _legislator(id={"bioguide": "A111111"}, name={"first": "John", "last": "Smith"}),
        _legislator(id={"bioguide": "B222222"}, name={"first": "Jane", "last": "Smith"}),
    ]
    identity = resolve_politician_identity(
        first_name="Jane",
        last_name="Smith",
        reference_date=datetime(2026, 6, 1, tzinfo=UTC),
        legislators=legislators,
    )
    assert identity["bioguide_id"] == "B222222"


def test_resolve_politician_identity_no_match_resolves_to_none() -> None:
    """ "Missing stays missing" — no fabricated bioguide id for an unmatched
    or still-ambiguous name."""
    legislators = [_legislator()]
    identity = resolve_politician_identity(
        first_name="Nobody",
        last_name="Nonexistent",
        reference_date=datetime(2026, 6, 1, tzinfo=UTC),
        legislators=legislators,
    )
    assert identity == {"bioguide_id": None, "state": None, "party": None}


def test_build_committee_assignments_matches_by_bioguide_and_skips_non_senate() -> None:
    """PROMPT.md Phase 19 implement item 3."""
    membership = {
        "SSBK": [{"name": "Mitch McConnell", "bioguide": "M000355"}],
        "SSAF13": [{"name": "Mitch McConnell", "bioguide": "M000355"}],  # subcommittee, skipped
        "HSAG": [{"name": "Someone Else", "bioguide": "X000000"}],  # different politician
    }
    committees_by_id = {
        "SSBK": {
            "type": "senate",
            "name": "Senate Committee on Banking, Housing, and Urban Affairs",
            "jurisdiction": "Banking and monetary policy.",
        },
        "HSAG": {"type": "house", "name": "House Committee on Agriculture"},
    }
    assignments = build_committee_assignments(
        "M000355", membership, committees_by_id, "s1", datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert len(assignments) == 1
    assert assignments[0].committee_thomas_id == "SSBK"
    assert assignments[0].chamber == Chamber.SENATE


def _politician_txn(**overrides: object) -> PoliticianTransaction:
    defaults: dict[str, object] = {
        "politician_bioguide_id": "M000355",
        "politician_name": "Mitch McConnell",
        "chamber": Chamber.SENATE,
        "report_id": "r1",
        "filed_at": datetime(2026, 1, 20, tzinfo=UTC),
        "transaction_date": datetime(2026, 1, 15, tzinfo=UTC),
        "owner": PoliticianOwner.SELF,
        "ticker": "UHS",
        "asset_name": "Universal Health Services, Inc. Common Stock",
        "asset_type": "Stock",
        "transaction_type": PoliticianTransactionType.PURCHASE,
        "range_low": 1001.0,
        "range_high": 15000.0,
        "filing_delay_days": 5,
        "source_record_id": "s1",
        "synced_at": datetime(2026, 1, 20, tzinfo=UTC),
    }
    defaults.update(overrides)
    return PoliticianTransaction(**defaults)  # type: ignore[arg-type]


def test_compute_politician_trade_profile_sums_ranges_independently() -> None:
    """PROMPT.md Phase 19 verification 1 applied to the aggregate: low and
    high bounds are summed independently, never averaged into one number."""
    purchase1 = _politician_txn(
        transaction_type=PoliticianTransactionType.PURCHASE,
        range_low=1001.0,
        range_high=15000.0,
        transaction_date=datetime(2026, 1, 1, tzinfo=UTC),
    )
    purchase2 = _politician_txn(
        transaction_type=PoliticianTransactionType.PURCHASE,
        range_low=15001.0,
        range_high=50000.0,
        transaction_date=datetime(2026, 2, 1, tzinfo=UTC),
    )
    sale = _politician_txn(
        transaction_type=PoliticianTransactionType.SALE_FULL,
        range_low=50001.0,
        range_high=100000.0,
        transaction_date=datetime(2026, 3, 1, tzinfo=UTC),
    )
    profile = compute_politician_trade_profile(
        "M000355", "Mitch McConnell", [purchase1, purchase2, sale]
    )
    assert profile is not None
    assert profile.total_purchased_range_low == 16002.0
    assert profile.total_purchased_range_high == 65000.0
    assert profile.total_sold_range_low == 50001.0
    assert profile.total_sold_range_high == 100000.0


def test_compute_politician_trade_profile_open_ended_total_is_unbounded() -> None:
    bounded = _politician_txn(range_low=1001.0, range_high=15000.0)
    unbounded = _politician_txn(range_low=50000000.0, range_high=None)
    profile = compute_politician_trade_profile("M000355", "Mitch McConnell", [bounded, unbounded])
    assert profile is not None
    assert profile.total_purchased_range_high is None


def test_compute_politician_trade_profile_none_for_no_transactions() -> None:
    assert compute_politician_trade_profile("M000355", "Mitch McConnell", []) is None


def test_compute_bracket_size_anomaly_requires_two_prior_transactions() -> None:
    latest = _politician_txn(range_low=50000.0, transaction_date=datetime(2026, 3, 1, tzinfo=UTC))
    one_prior = [
        _politician_txn(range_low=1001.0, transaction_date=datetime(2026, 1, 1, tzinfo=UTC)),
        latest,
    ]
    assert compute_bracket_size_anomaly(latest, one_prior) is None


def test_compute_bracket_size_anomaly_never_claims_an_exact_amount() -> None:
    """PROMPT.md Phase 19 verification 1."""
    latest = _politician_txn(range_low=100000.0, transaction_date=datetime(2026, 3, 1, tzinfo=UTC))
    history = [
        _politician_txn(range_low=1000.0, transaction_date=datetime(2026, 1, 1, tzinfo=UTC)),
        _politician_txn(range_low=1000.0, transaction_date=datetime(2026, 2, 1, tzinfo=UTC)),
        latest,
    ]
    feature = compute_bracket_size_anomaly(latest, history)
    assert feature is not None
    assert feature.value == 100.0
    assert "never an exact transaction amount" in feature.baseline_description
    assert "disclosed bracket floors" in feature.baseline_description
    assert feature.is_notable is True


def test_compute_politician_cluster_feature_counts_distinct_members_in_window() -> None:
    target = _politician_txn(
        politician_bioguide_id="cik1",
        transaction_type=PoliticianTransactionType.PURCHASE,
        transaction_date=datetime(2026, 3, 1, tzinfo=UTC),
    )
    same_week = _politician_txn(
        politician_bioguide_id="cik2",
        transaction_type=PoliticianTransactionType.PURCHASE,
        transaction_date=datetime(2026, 3, 3, tzinfo=UTC),
    )
    outside_window = _politician_txn(
        politician_bioguide_id="cik3",
        transaction_type=PoliticianTransactionType.PURCHASE,
        transaction_date=datetime(2026, 4, 1, tzinfo=UTC),
    )
    different_direction = _politician_txn(
        politician_bioguide_id="cik4",
        transaction_type=PoliticianTransactionType.SALE_FULL,
        transaction_date=datetime(2026, 3, 2, tzinfo=UTC),
    )
    feature = compute_politician_cluster_feature(
        target, [target, same_week, outside_window, different_direction]
    )
    assert feature is not None
    assert feature.value == 2.0
    assert "within 7 days" in feature.baseline_description


def test_compute_politician_cluster_feature_none_for_exchange() -> None:
    txn = _politician_txn(transaction_type=PoliticianTransactionType.EXCHANGE)
    assert compute_politician_cluster_feature(txn, [txn]) is None


def test_compute_committee_relationship_features_finds_real_keyword_overlap() -> None:
    """PROMPT.md Phase 19 implement item 9 / verification 4: every
    relationship can be inspected — the committee name, jurisdiction
    excerpt, and matched terms are all present in the returned feature."""
    txn = _politician_txn(ticker="UHS", asset_name="Universal Health Services")
    assignment = CommitteeAssignment(
        politician_bioguide_id="M000355",
        committee_thomas_id="SSHR",
        committee_name="Senate Committee on Health, Education, Labor, and Pensions",
        chamber=Chamber.SENATE,
        jurisdiction_text=(
            "The Senate Committee on Health, Education, Labor, and Pensions has jurisdiction "
            "over most of the agencies, institutes, and programs of the Department of Health "
            "and Human Services."
        ),
        source_record_id="s1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    features = compute_committee_relationship_features(txn, [assignment], "Health Care")
    assert len(features) == 1
    assert features[0].feature_name == "committee_jurisdiction_overlap"
    assert "Senate Committee on Health, Education, Labor, and Pensions" in (
        features[0].baseline_description
    )
    assert "health" in features[0].baseline_description.lower()


def test_compute_committee_relationship_features_never_claims_misconduct() -> None:
    """PROMPT.md Phase 19 verification 3: correlation is not described as
    proof of misconduct."""
    txn = _politician_txn(ticker="UHS", asset_name="Universal Health Services")
    assignment = CommitteeAssignment(
        politician_bioguide_id="M000355",
        committee_thomas_id="SSHR",
        committee_name="Senate Committee on Health, Education, Labor, and Pensions",
        chamber=Chamber.SENATE,
        jurisdiction_text="Jurisdiction over health and human services programs.",
        source_record_id="s1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    features = compute_committee_relationship_features(txn, [assignment], "Health Care")
    assert len(features) == 1
    description = features[0].baseline_description.lower()
    for banned in ("suspicious", "illegal", "insider trading", "fraud", "misconduct", "proof"):
        assert banned not in description


def test_compute_committee_relationship_features_empty_when_no_overlap() -> None:
    txn = _politician_txn(ticker="UHS", asset_name="Universal Health Services")
    assignment = CommitteeAssignment(
        politician_bioguide_id="M000355",
        committee_thomas_id="SSAF",
        committee_name="Senate Committee on Agriculture, Nutrition, and Forestry",
        chamber=Chamber.SENATE,
        jurisdiction_text="Legislative jurisdiction over agriculture, food, and nutrition.",
        source_record_id="s1",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert compute_committee_relationship_features(txn, [assignment], "Health Care") == []


def test_compute_committee_relationship_features_empty_when_no_industry() -> None:
    txn = _politician_txn()
    assert compute_committee_relationship_features(txn, [], None) == []
