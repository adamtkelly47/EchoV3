from datetime import UTC, datetime

import pytest

from core.errors import ProviderUnavailableError
from core.time import FakeClock
from domains.portfolio.errors import (
    SchwabCredentialNotFoundError,
    SchwabReauthorizationRequiredError,
    SchwabTokenRefreshError,
)
from domains.portfolio.service import PortfolioService
from infrastructure.secrets.encryption import SecretCipher
from tests.unit.domains.portfolio.fakes import (
    FakeAuditRepository,
    FakePortfolioRepository,
    FakeSchwabCredentialRepository,
    FakeSchwabProvider,
    FakeSourceRecordRepository,
)

_FERNET_KEY = "qgiLfl_Ze3gvcItoR_vV0K0D0IWKj2I8gA_U9Rq95EY="


def _service(
    clock: FakeClock | None = None, provider: FakeSchwabProvider | None = None
) -> tuple[
    PortfolioService, FakeSchwabProvider, FakePortfolioRepository, FakeSchwabCredentialRepository
]:
    clock = clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    provider = provider or FakeSchwabProvider()
    portfolio_repo = FakePortfolioRepository()
    credentials = FakeSchwabCredentialRepository()
    service = PortfolioService(
        credentials,
        portfolio_repo,
        FakeSourceRecordRepository(),
        provider,
        SecretCipher(_FERNET_KEY),
        FakeAuditRepository(),
        clock,
        "state-secret",
    )
    return service, provider, portfolio_repo, credentials


async def _connect(service: PortfolioService, user_id: str = "user_1") -> None:
    state = service.start_authorization(user_id)
    state_value = state.split("state=", 1)[1]
    await service.complete_authorization("auth-code", state_value)


async def test_connect_stores_encrypted_tokens_and_refresh_expiry() -> None:
    service, _, _, credentials = _service()
    await _connect(service)

    stored = await credentials.get_for_user("user_1")
    assert stored is not None
    assert stored.encrypted_access_token != "fake-access-token"
    assert stored.refresh_token_expires_at == datetime(2026, 1, 8, tzinfo=UTC)


async def test_sync_masks_account_number_and_reconciles() -> None:
    service, provider, portfolio_repo, _ = _service()
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
    service, provider, portfolio_repo, _ = _service()
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
    service, provider, _, _ = _service()
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
    service, provider, portfolio_repo, _ = _service()
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
    service, provider, _, _ = _service()
    await _connect(service)
    provider.quotes_response = {"AAPL": {"quote": {"lastPrice": 185.5, "netChange": 1.5}}}

    quotes = await service.get_quotes("user_1", ["AAPL"])

    assert quotes[0].price == 185.5


async def test_expired_access_token_triggers_refresh() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, _, credentials = _service(clock=clock)
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
    service, provider, _, _ = _service(clock=clock)
    await _connect(service)

    clock.set(datetime(2026, 1, 9, tzinfo=UTC))  # past the 7-day refresh token expiry
    with pytest.raises(SchwabReauthorizationRequiredError):
        await service.sync("user_1")

    assert not any(c[0] == "refresh_access_token" for c in provider.calls)


async def test_token_refresh_provider_failure_surfaces_as_schwab_error() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service, provider, _, _ = _service(clock=clock)
    await _connect(service)
    provider.raise_on_refresh = ProviderUnavailableError("Schwab rejected the refresh token")

    clock.set(datetime(2026, 1, 1, 12, 27, 0, tzinfo=UTC))
    with pytest.raises(SchwabTokenRefreshError):
        await service.sync("user_1")


async def test_sync_without_credential_raises_not_found() -> None:
    service, _, _, _ = _service()
    with pytest.raises(SchwabCredentialNotFoundError):
        await service.sync("never_connected")
