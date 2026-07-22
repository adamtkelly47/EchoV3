from datetime import UTC, datetime

import pytest

from core.errors import ProviderUnavailableError
from core.time import FakeClock
from domains.portfolio.errors import (
    HypotheticalTradeAlreadyClosedError,
    HypotheticalTradeNotFoundError,
    IPSValidationError,
    NoActiveIPSError,
    PortfolioSnapshotNotFoundError,
    QuotePriceUnavailableError,
    SchwabCredentialNotFoundError,
    SchwabReauthorizationRequiredError,
    SchwabTokenRefreshError,
)
from domains.portfolio.models import AssetType, HypotheticalTradeAction, HypotheticalTradeStatus
from domains.portfolio.schemas import AllocationRange, ConcentrationRule, RestrictedSecurity
from domains.portfolio.service import PortfolioService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.portfolio.fakes import (
    FakeAuditRepository,
    FakeComplianceResultRepository,
    FakeComputedValueRecordRepository,
    FakeHypotheticalTradeRepository,
    FakeIPSRepository,
    FakePortfolioRepository,
    FakeSchwabCredentialRepository,
    FakeSchwabProvider,
    FakeSourceRecordRepository,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _service(
    clock: FakeClock | None = None, provider: FakeSchwabProvider | None = None
) -> tuple[
    PortfolioService,
    FakeSchwabProvider,
    FakePortfolioRepository,
    FakeSchwabCredentialRepository,
    FakeIPSRepository,
]:
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = provider or FakeSchwabProvider()
    portfolio_repo = FakePortfolioRepository()
    credentials = FakeSchwabCredentialRepository()
    ips_repo = FakeIPSRepository()
    service = PortfolioService(
        credentials,
        portfolio_repo,
        FakeSourceRecordRepository(),
        provider,
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        clock,
        "state-secret",
        FakeComputedValueRecordRepository(),
        ips_repo,
        FakeComplianceResultRepository(),
        FakeHypotheticalTradeRepository(),
    )
    return service, provider, portfolio_repo, credentials, ips_repo


async def _connect(service: PortfolioService, user_id: str = "user_1") -> None:
    state = service.start_authorization(user_id)
    state_value = state.split("state=", 1)[1]
    await service.complete_authorization("auth-code", state_value)


async def test_is_connected_reflects_credential_presence() -> None:
    """PROMPT.md Phase 22 implement item 6: "integration status.\" """
    service, _, _, _, _ = _service()
    assert await service.is_connected("user_1") is False

    await _connect(service)
    assert await service.is_connected("user_1") is True


async def test_connect_stores_encrypted_tokens_and_refresh_expiry() -> None:
    service, _, _, credentials, _ = _service()
    await _connect(service)

    stored = await credentials.get_for_user("user_1")
    assert stored is not None
    assert stored.encrypted_access_token != "fake-access-token"
    assert stored.refresh_token_expires_at == datetime(2026, 1, 8, tzinfo=UTC)


async def test_sync_masks_account_number_and_reconciles() -> None:
    service, provider, portfolio_repo, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "87654321", "hashValue": "hash-abc"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "87654321",
                "currentBalances": {"cashBalance": 5000.0, "liquidationValue": 23500.0},
                "positions": [
                    {
                        "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                        "longQuantity": 100,
                        "shortQuantity": 0,
                        "marketValue": 18500.0,
                        "averagePrice": 175.0,
                    }
                ],
            }
        }
    ]

    snapshot = await service.sync("user_1")

    assert snapshot.reconciled is True
    assert snapshot.total_market_value == 23500.0
    accounts = await portfolio_repo.list_accounts("user_1")
    assert accounts[0].display_mask == "••••4321"
    assert accounts[0].account_hash == "hash-abc"


async def test_repeated_sync_reuses_the_same_account_and_position_rows() -> None:
    """Regression for a real bug found live (Docs/DECISION_LOG.md's Phase 12
    entry): re-syncing must update the *same* account/position rows, not
    silently create a fresh, never-reused account_id (and therefore
    orphaned positions) on every call."""
    service, provider, portfolio_repo, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "87654321", "hashValue": "hash-abc"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "87654321",
                "currentBalances": {"cashBalance": 5000.0, "liquidationValue": 23500.0},
                "positions": [
                    {
                        "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                        "longQuantity": 100,
                        "shortQuantity": 0,
                        "marketValue": 18500.0,
                        "averagePrice": 175.0,
                    }
                ],
            }
        }
    ]

    first_snapshot = await service.sync("user_1")
    second_snapshot = await service.sync("user_1")

    assert first_snapshot.account_ids == second_snapshot.account_ids
    accounts = await portfolio_repo.list_accounts("user_1")
    assert len(accounts) == 1  # not two, one per sync

    positions = await portfolio_repo.list_positions("user_1", accounts[0].account_id)
    assert len(positions) == 1  # not two — the same AAPL row updated, not duplicated


async def test_sync_reconciliation_mismatch_produces_warning() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "11111111", "hashValue": "hash-1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "11111111",
                "currentBalances": {"cashBalance": 100.0, "liquidationValue": 99999.0},
                "positions": [],
            }
        }
    ]

    snapshot = await service.sync("user_1")

    assert snapshot.reconciled is False
    assert any("mismatch" in w for w in snapshot.warnings)


async def test_sync_stores_raw_response_for_provenance() -> None:
    service, provider, portfolio_repo, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "11111111", "hashValue": "hash-1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "11111111",
                "currentBalances": {"cashBalance": 100.0, "liquidationValue": 100.0},
                "positions": [],
            }
        }
    ]

    await service.sync("user_1")

    assert len(portfolio_repo.raw_responses) == 1


async def test_get_quotes_returns_parsed_quote() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 185.5, "netChange": 1.5}}}

    quotes = await service.get_quotes("user_1", ["AAPL"])

    assert quotes[0].price == 185.5


async def test_expired_access_token_triggers_refresh() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, _, credentials, _ = _service(clock=clock)
    await _connect(service)

    clock.set(datetime(2026, 1, 1, 12, 27, 0, tzinfo=UTC))  # inside the 5-minute refresh buffer
    provider.accounts_response = []
    provider.account_numbers_response = []
    await service.sync("user_1")

    assert any(c[0] == "refresh_access_token" for c in provider.calls)


async def test_refresh_token_expired_raises_reauthorization_required_not_a_refresh_attempt() -> (
    None
):
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service, provider, _, _, _ = _service(clock=clock)
    await _connect(service)

    clock.set(datetime(2026, 1, 9, tzinfo=UTC))  # past the 7-day refresh token expiry
    with pytest.raises(SchwabReauthorizationRequiredError):
        await service.sync("user_1")

    assert not any(c[0] == "refresh_access_token" for c in provider.calls)


async def test_token_refresh_provider_failure_surfaces_as_schwab_error() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, _, _, _ = _service(clock=clock)
    await _connect(service)
    provider.raise_on_refresh = ProviderUnavailableError("Schwab rejected the refresh token")

    clock.set(datetime(2026, 1, 1, 12, 27, 0, tzinfo=UTC))
    with pytest.raises(SchwabTokenRefreshError):
        await service.sync("user_1")


async def test_sync_without_credential_raises_not_found() -> None:
    service, _, _, _, _ = _service()
    with pytest.raises(SchwabCredentialNotFoundError):
        await service.sync("never_connected")


async def test_get_dashboard_without_a_sync_raises_snapshot_not_found() -> None:
    service, _, _, _, _ = _service()
    await _connect(service)
    with pytest.raises(PortfolioSnapshotNotFoundError):
        await service.get_dashboard("user_1")


async def test_get_dashboard_computes_weights_gain_loss_and_provenance() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "87654321", "hashValue": "hash-abc"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "87654321",
                "currentBalances": {"cashBalance": 5000.0, "liquidationValue": 23500.0},
                "positions": [
                    {
                        "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                        "longQuantity": 100,
                        "shortQuantity": 0,
                        "marketValue": 18500.0,
                        "averagePrice": 150.0,
                    }
                ],
            }
        }
    ]
    await service.sync("user_1")

    dashboard = await service.get_dashboard("user_1")

    assert dashboard.total_market_value == 23500.0
    assert dashboard.reconciled is True
    assert dashboard.position_weights[0].symbol == "AAPL"
    assert dashboard.unrealized_gain_loss[0].unrealized_gain_loss_dollar == 3500.0
    assert dashboard.total_unrealized_gain_loss_dollar == 3500.0
    assert dashboard.sector_exposure[0].sector == "Unknown"
    assert dashboard.computed_value_record_id
    assert not dashboard.is_stale


async def test_get_dashboard_flags_stale_data() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    service, provider, _, _, _ = _service(clock=clock)
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "11111111", "hashValue": "hash-1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "11111111",
                "currentBalances": {"cashBalance": 100.0, "liquidationValue": 100.0},
                "positions": [],
            }
        }
    ]
    await service.sync("user_1")

    clock.set(datetime(2026, 1, 3, tzinfo=UTC))  # more than 24 hours later
    dashboard = await service.get_dashboard("user_1")

    assert dashboard.is_stale is True


async def test_get_dashboard_uses_active_ips_concentration_threshold() -> None:
    """PROMPT.md Phase 13's own comment promised this: once an IPS exists,
    its concentration_rule supersedes Phase 13's generic 10% default."""
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "11111111", "hashValue": "hash-1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "11111111",
                "currentBalances": {"cashBalance": 0.0, "liquidationValue": 10000.0},
                "positions": [
                    {
                        "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                        "longQuantity": 100,
                        "shortQuantity": 0,
                        "marketValue": 10000.0,
                    }
                ],
            }
        }
    ]
    await service.sync("user_1")

    # 100% concentration wouldn't breach a 10% default threshold... it would
    # (100 > 10), so instead prove the *IPS's own* threshold is what's used:
    # set an IPS limit of 50%, still breached at 100%, confirming the IPS
    # value (not the 10% default) is what's actually being compared.
    await service.create_ips_version(
        "user_1",
        None,
        [],
        [],
        ConcentrationRule(max_position_percent=50.0),
        [],
    )
    dashboard = await service.get_dashboard("user_1")

    assert dashboard.concentration_warnings[0].threshold_percent == 50.0


async def test_create_ips_version_rejects_invalid_allocation_range() -> None:
    service, _, _, _, _ = _service()
    with pytest.raises(IPSValidationError):
        await service.create_ips_version(
            "user_1",
            None,
            [],
            [AllocationRange(asset_type=AssetType.EQUITY, min_percent=80.0, max_percent=50.0)],
            ConcentrationRule(max_position_percent=25.0),
            [],
        )


async def test_create_ips_version_increments_and_supersedes() -> None:
    service, _, _, _, ips_repo = _service()
    first = await service.create_ips_version(
        "user_1", None, [], [], ConcentrationRule(max_position_percent=25.0), []
    )
    second = await service.create_ips_version(
        "user_1", first.ips_id, [], [], ConcentrationRule(max_position_percent=20.0), []
    )

    assert second.version_number == 2
    assert second.is_active is True

    active = await ips_repo.get_active("user_1")
    assert active is not None
    assert active.version_id == second.version_id

    versions = await service.list_ips_versions("user_1")
    assert len(versions) == 2
    first_stored = next(v for v in versions if v.version_id == first.version_id)
    assert first_stored.is_active is False
    # The superseded version's own rules are untouched — only its active
    # flag changed (PROMPT.md Phase 14 verification 3).
    assert first_stored.concentration_rule.max_position_percent == 25.0


async def test_evaluate_ips_compliance_without_active_ips_raises() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "1", "hashValue": "h1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "1",
                "currentBalances": {"cashBalance": 0.0, "liquidationValue": 0.0},
                "positions": [],
            }
        }
    ]
    await service.sync("user_1")
    with pytest.raises(NoActiveIPSError):
        await service.evaluate_ips_compliance("user_1")


async def test_evaluate_ips_compliance_without_sync_raises_snapshot_not_found() -> None:
    service, _, _, _, _ = _service()
    await service.create_ips_version(
        "user_1", None, [], [], ConcentrationRule(max_position_percent=25.0), []
    )
    with pytest.raises(PortfolioSnapshotNotFoundError):
        await service.evaluate_ips_compliance("user_1")


async def test_evaluate_ips_compliance_cites_ips_version_and_snapshot() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "1", "hashValue": "h1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "1",
                "currentBalances": {"cashBalance": 0.0, "liquidationValue": 10000.0},
                "positions": [
                    {
                        "instrument": {"symbol": "TSLA", "assetType": "EQUITY"},
                        "longQuantity": 10,
                        "shortQuantity": 0,
                        "marketValue": 10000.0,
                    }
                ],
            }
        }
    ]
    snapshot = await service.sync("user_1")
    ips = await service.create_ips_version(
        "user_1",
        None,
        [],
        [],
        ConcentrationRule(max_position_percent=25.0),
        [RestrictedSecurity(symbol="TSLA")],
    )

    result = await service.evaluate_ips_compliance("user_1")

    assert result.ips_version_id == ips.version_id
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.compliant is False
    breach_types = {b.rule_type for b in result.breaches}
    assert "concentration" in breach_types
    assert "restricted_security" in breach_types

    latest = await service.get_latest_compliance_result("user_1")
    assert latest is not None
    assert latest.result_id == result.result_id


async def test_updating_ips_does_not_rewrite_a_historical_compliance_result() -> None:
    """PROMPT.md Phase 14 verification 3: updating an IPS does not rewrite
    historical evaluations — a result already cites a specific
    ips_version_id, and that citation must stay valid and retrievable even
    after a newer version becomes active."""
    service, provider, _, _, ips_repo = _service()
    await _connect(service)
    provider.account_numbers_response = [{"accountNumber": "1", "hashValue": "h1"}]
    provider.accounts_response = [
        {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "1",
                "currentBalances": {"cashBalance": 0.0, "liquidationValue": 10000.0},
                "positions": [],
            }
        }
    ]
    await service.sync("user_1")
    first_ips = await service.create_ips_version(
        "user_1", None, [], [], ConcentrationRule(max_position_percent=25.0), []
    )
    first_result = await service.evaluate_ips_compliance("user_1")
    assert first_result.ips_version_id == first_ips.version_id

    await service.create_ips_version(
        "user_1", first_ips.ips_id, [], [], ConcentrationRule(max_position_percent=5.0), []
    )

    # The old result's citation is untouched by the new version existing.
    unchanged = await ips_repo.get_version(first_ips.version_id)
    assert unchanged is not None
    assert unchanged.concentration_rule.max_position_percent == 25.0
    assert first_result.ips_version_id == first_ips.version_id


# --- PROMPT.md Phase 27: paper trading observation. No test here (or
# anywhere in domains/portfolio/service.py) ever calls an order/execute
# method — none exists to call. ---


async def test_propose_hypothetical_trade_uses_a_real_just_fetched_quote() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 150.0}}}

    trade = await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="Strong earnings beat expected next quarter",
        expected_outcome="Price rises at least 5% within 30 days",
        expected_horizon_days=30,
        rationale_references=["thesis_123"],
    )
    assert trade.hypothetical_price == 150.0
    assert trade.status == HypotheticalTradeStatus.OPEN
    assert trade.rationale_references == ["thesis_123"]


async def test_propose_hypothetical_trade_raises_when_no_price_available() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {}}}

    with pytest.raises(QuotePriceUnavailableError):
        await service.propose_hypothetical_trade(
            "user_1",
            symbol="AAPL",
            action=HypotheticalTradeAction.BUY,
            quantity=10,
            rationale="r",
            expected_outcome="e",
            expected_horizon_days=30,
        )


async def test_record_hypothetical_performance_sample_computes_real_gain_loss() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    trade = await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )

    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 110.0}}}
    sample = await service.record_hypothetical_performance_sample(trade.trade_id)
    assert sample.price == 110.0
    assert sample.gain_loss_percent == pytest.approx(10.0)


async def test_close_hypothetical_trade_requires_a_review_note_and_is_terminal() -> None:
    """PROMPT.md Phase 27 capability 8: "review failures.\" """
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    trade = await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )

    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 90.0}}}
    closed = await service.close_hypothetical_trade(
        trade.trade_id, review_note="Thesis did not play out — earnings missed"
    )
    assert closed.status == HypotheticalTradeStatus.CLOSED
    assert closed.closing_price == 90.0
    assert closed.review_note == "Thesis did not play out — earnings missed"

    with pytest.raises(HypotheticalTradeAlreadyClosedError):
        await service.close_hypothetical_trade(trade.trade_id, review_note="again")


async def test_get_hypothetical_trade_raises_when_missing() -> None:
    service, _, _, _, _ = _service()
    with pytest.raises(HypotheticalTradeNotFoundError):
        await service.get_hypothetical_trade("does-not-exist")


async def test_list_hypothetical_trades_for_user_scopes_correctly() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    await _connect(service, user_id="user_2")
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )
    await service.propose_hypothetical_trade(
        "user_2",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )
    trades = await service.list_hypothetical_trades_for_user("user_1")
    assert len(trades) == 1
    assert trades[0].user_id == "user_1"


async def test_evaluate_hypothetical_trade_compares_against_no_action_and_thesis_quality() -> None:
    """PROMPT.md Phase 27 capabilities 5-7: "compare against no action,"
    "measure thesis quality," "measure timing.\" """
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    trade = await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )

    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 108.0}}}
    await service.record_hypothetical_performance_sample(trade.trade_id)

    evaluation = await service.evaluate_hypothetical_trade(trade.trade_id)
    assert evaluation.gain_loss_percent == pytest.approx(8.0)
    assert evaluation.comparison_vs_no_action_percent == pytest.approx(8.0)
    assert evaluation.thesis_direction_correct is True
    assert evaluation.days_to_realize == 0


async def test_evaluate_hypothetical_trade_with_no_samples_is_honestly_unknown() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    trade = await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.BUY,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )

    evaluation = await service.evaluate_hypothetical_trade(trade.trade_id)
    assert evaluation.gain_loss_percent is None
    assert evaluation.thesis_direction_correct is None
    assert evaluation.days_to_realize is None


async def test_evaluate_hypothetical_trade_after_close_uses_the_closing_price() -> None:
    service, provider, _, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    trade = await service.propose_hypothetical_trade(
        "user_1",
        symbol="AAPL",
        action=HypotheticalTradeAction.SELL,
        quantity=10,
        rationale="r",
        expected_outcome="e",
        expected_horizon_days=30,
    )

    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 85.0}}}
    closed = await service.close_hypothetical_trade(trade.trade_id, review_note="thesis played out")
    assert closed.closing_price == 85.0

    evaluation = await service.evaluate_hypothetical_trade(trade.trade_id)
    assert evaluation.gain_loss_percent == pytest.approx(15.0)
    assert evaluation.thesis_direction_correct is True
