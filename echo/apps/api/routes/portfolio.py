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
    CompleteAuthorizationRequest,
    ConnectResponse,
    PriceHistoryPointResponse,
    PriceHistoryResponse,
    QuoteListResponse,
    QuoteResponse,
    SnapshotResponse,
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
