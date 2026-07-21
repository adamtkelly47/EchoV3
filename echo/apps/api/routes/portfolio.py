"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in query params, matching the established convention from
apps/api/routes/{conversations,memory,calendar}.py.

No OAuth callback route exists here, unlike apps/api/routes/calendar.py —
Schwab's registered redirect_uri is a fixed, unreachable 127.0.0.1 address
(see domains/portfolio/service.py's module docstring), so the user
completes the flow by pasting the resulting dead-page URL into
`/portfolio/schwab/oauth/complete` themselves.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session, get_portfolio_service
from apps.api.schemas.portfolio import (
    AccountListResponse,
    AccountResponse,
    AssetClassExposureResponse,
    CompleteAuthorizationRequest,
    ConcentrationWarningResponse,
    ConnectResponse,
    MoneyDashboardResponse,
    PositionGainLossResponse,
    PositionWeightResponse,
    PriceHistoryPointResponse,
    PriceHistoryResponse,
    QuoteListResponse,
    QuoteResponse,
    SectorExposureResponse,
    SnapshotResponse,
    SymbolExposureResponse,
)
from domains.portfolio.service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/schwab/oauth/authorize")
async def authorize(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> RedirectResponse:
    return RedirectResponse(portfolio.start_authorization(user_id))


@router.post("/schwab/oauth/complete", response_model=ConnectResponse)
async def complete_authorization(
    body: CompleteAuthorizationRequest,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectResponse:
    credential = await portfolio.complete_authorization(body.redirect_value, body.state)
    await session.commit()
    return ConnectResponse(user_id=credential.user_id, connected=True)


@router.post("/sync", response_model=SnapshotResponse)
async def sync(
    user_id: str,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> SnapshotResponse:
    snapshot = await portfolio.sync(user_id)
    await session.commit()
    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        user_id=snapshot.user_id,
        taken_at=snapshot.taken_at,
        total_market_value=snapshot.total_market_value,
        reconciled=snapshot.reconciled,
        reconciliation_diff=snapshot.reconciliation_diff,
        account_ids=snapshot.account_ids,
        warnings=snapshot.warnings,
    )


@router.get("/accounts", response_model=AccountListResponse)
async def accounts(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> AccountListResponse:
    result = await portfolio.get_accounts(user_id)
    return AccountListResponse(
        accounts=[
            AccountResponse(
                account_id=a.account_id,
                account_hash=a.account_hash,
                display_mask=a.display_mask,
                account_type=a.account_type,
                synced_at=a.synced_at,
            )
            for a in result
        ]
    )


@router.get("/snapshot", response_model=SnapshotResponse | None)
async def latest_snapshot(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> SnapshotResponse | None:
    snapshot = await portfolio.get_latest_snapshot(user_id)
    if snapshot is None:
        return None
    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        user_id=snapshot.user_id,
        taken_at=snapshot.taken_at,
        total_market_value=snapshot.total_market_value,
        reconciled=snapshot.reconciled,
        reconciliation_diff=snapshot.reconciliation_diff,
        account_ids=snapshot.account_ids,
        warnings=snapshot.warnings,
    )


@router.get("/dashboard", response_model=MoneyDashboardResponse)
async def dashboard(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> MoneyDashboardResponse:
    result = await portfolio.get_dashboard(user_id)
    return MoneyDashboardResponse(
        user_id=result.user_id,
        generated_at=result.generated_at,
        last_verified_sync_at=result.last_verified_sync_at,
        is_stale=result.is_stale,
        total_market_value=result.total_market_value,
        reconciled=result.reconciled,
        position_weights=[
            PositionWeightResponse(
                symbol=w.symbol,
                account_id=w.account_id,
                market_value=w.market_value,
                weight_percent=w.weight_percent,
            )
            for w in result.position_weights
        ],
        asset_class_exposure=[
            AssetClassExposureResponse(
                asset_type=e.asset_type.value,
                market_value=e.market_value,
                weight_percent=e.weight_percent,
            )
            for e in result.asset_class_exposure
        ],
        sector_exposure=[
            SectorExposureResponse(
                sector=s.sector, market_value=s.market_value, weight_percent=s.weight_percent
            )
            for s in result.sector_exposure
        ],
        cross_account_exposure=[
            SymbolExposureResponse(
                symbol=x.symbol,
                total_quantity=x.total_quantity,
                total_market_value=x.total_market_value,
                account_ids=x.account_ids,
            )
            for x in result.cross_account_exposure
        ],
        concentration_warnings=[
            ConcentrationWarningResponse(
                symbol=c.symbol,
                weight_percent=c.weight_percent,
                threshold_percent=c.threshold_percent,
            )
            for c in result.concentration_warnings
        ],
        unrealized_gain_loss=[
            PositionGainLossResponse(
                symbol=g.symbol,
                account_id=g.account_id,
                quantity=g.quantity,
                cost_basis=g.cost_basis,
                market_value=g.market_value,
                unrealized_gain_loss_dollar=g.unrealized_gain_loss_dollar,
                unrealized_gain_loss_percent=g.unrealized_gain_loss_percent,
            )
            for g in result.unrealized_gain_loss
        ],
        total_unrealized_gain_loss_dollar=result.total_unrealized_gain_loss_dollar,
        warnings=result.warnings,
        computed_value_record_id=result.computed_value_record_id,
    )


@router.get("/quotes", response_model=QuoteListResponse)
async def quotes(
    user_id: str, symbols: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> QuoteListResponse:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    result = await portfolio.get_quotes(user_id, symbol_list)
    return QuoteListResponse(
        quotes=[
            QuoteResponse(
                symbol=q.symbol,
                price=q.price,
                change_dollar=q.change_dollar,
                change_percent=q.change_percent,
                retrieved_at=q.retrieved_at,
            )
            for q in result
        ]
    )


@router.get("/price-history/{symbol}", response_model=PriceHistoryResponse)
async def price_history(
    symbol: str, user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> PriceHistoryResponse:
    points = await portfolio.get_price_history(user_id, symbol)
    return PriceHistoryResponse(
        symbol=symbol,
        points=[
            PriceHistoryPointResponse(
                timestamp=p.timestamp,
                open=p.open,
                high=p.high,
                low=p.low,
                close=p.close,
                volume=p.volume,
            )
            for p in points
        ],
    )
