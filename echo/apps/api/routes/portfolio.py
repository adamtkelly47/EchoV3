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
    AllocationRangeResponse,
    AssetClassExposureResponse,
    CloseHypotheticalTradeRequest,
    CompleteAuthorizationRequest,
    ComplianceBreachResponse,
    ComplianceResultResponse,
    ConcentrationWarningResponse,
    ConnectResponse,
    CreateIPSVersionRequest,
    HypotheticalPerformanceSampleResponse,
    HypotheticalTradeEvaluationResponse,
    HypotheticalTradeResponse,
    IPSVersionListResponse,
    IPSVersionResponse,
    MoneyDashboardResponse,
    PositionGainLossResponse,
    PositionWeightResponse,
    PriceHistoryPointResponse,
    PriceHistoryResponse,
    ProposeHypotheticalTradeRequest,
    QuoteListResponse,
    QuoteResponse,
    RestrictedSecurityResponse,
    SectorExposureResponse,
    SnapshotResponse,
    SymbolExposureResponse,
)
from domains.portfolio.models import AssetType, HypotheticalTradeAction
from domains.portfolio.schemas import (
    AllocationRange,
    ComplianceResult,
    ConcentrationRule,
    HypotheticalPerformanceSample,
    HypotheticalTrade,
    HypotheticalTradeEvaluation,
    IPSVersion,
)
from domains.portfolio.schemas import RestrictedSecurity as DomainRestrictedSecurity
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


def _to_ips_response(version: IPSVersion) -> IPSVersionResponse:
    return IPSVersionResponse(
        version_id=version.version_id,
        ips_id=version.ips_id,
        version_number=version.version_number,
        user_id=version.user_id,
        account_ids=version.account_ids,
        allocation_ranges=[
            AllocationRangeResponse(
                asset_type=r.asset_type.value, min_percent=r.min_percent, max_percent=r.max_percent
            )
            for r in version.allocation_ranges
        ],
        max_position_percent=version.concentration_rule.max_position_percent,
        restricted_securities=[
            RestrictedSecurityResponse(symbol=r.symbol, reason=r.reason)
            for r in version.restricted_securities
        ],
        created_at=version.created_at,
        is_active=version.is_active,
    )


def _to_compliance_response(result: ComplianceResult) -> ComplianceResultResponse:
    return ComplianceResultResponse(
        result_id=result.result_id,
        user_id=result.user_id,
        ips_version_id=result.ips_version_id,
        snapshot_id=result.snapshot_id,
        evaluated_at=result.evaluated_at,
        compliant=result.compliant,
        breaches=[
            ComplianceBreachResponse(
                rule_type=b.rule_type, description=b.description, detail=b.detail
            )
            for b in result.breaches
        ],
    )


@router.post("/ips", response_model=IPSVersionResponse)
async def create_ips_version(
    user_id: str,
    body: CreateIPSVersionRequest,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> IPSVersionResponse:
    version = await portfolio.create_ips_version(
        user_id,
        body.ips_id,
        body.account_ids,
        [
            AllocationRange(
                asset_type=AssetType(r.asset_type),
                min_percent=r.min_percent,
                max_percent=r.max_percent,
            )
            for r in body.allocation_ranges
        ],
        ConcentrationRule(max_position_percent=body.max_position_percent),
        [
            DomainRestrictedSecurity(symbol=r.symbol, reason=r.reason)
            for r in body.restricted_securities
        ],
    )
    await session.commit()
    return _to_ips_response(version)


@router.get("/ips/active", response_model=IPSVersionResponse | None)
async def active_ips(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> IPSVersionResponse | None:
    version = await portfolio.get_active_ips(user_id)
    return _to_ips_response(version) if version is not None else None


@router.get("/ips/versions", response_model=IPSVersionListResponse)
async def ips_versions(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> IPSVersionListResponse:
    versions = await portfolio.list_ips_versions(user_id)
    return IPSVersionListResponse(versions=[_to_ips_response(v) for v in versions])


@router.post("/ips/compliance/evaluate", response_model=ComplianceResultResponse)
async def evaluate_compliance(
    user_id: str,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> ComplianceResultResponse:
    result = await portfolio.evaluate_ips_compliance(user_id)
    await session.commit()
    return _to_compliance_response(result)


@router.get("/ips/compliance/latest", response_model=ComplianceResultResponse | None)
async def latest_compliance_result(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> ComplianceResultResponse | None:
    result = await portfolio.get_latest_compliance_result(user_id)
    return _to_compliance_response(result) if result is not None else None


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


# --- PROMPT.md Phase 27: paper trading observation. No order/execute
# endpoint exists here or anywhere else in this router — enforced by
# omission, matching this module's own Schwab-connection precedent. ---


def _to_hypothetical_trade_response(trade: HypotheticalTrade) -> HypotheticalTradeResponse:
    return HypotheticalTradeResponse(
        trade_id=trade.trade_id,
        user_id=trade.user_id,
        symbol=trade.symbol,
        action=trade.action.value,
        quantity=trade.quantity,
        hypothetical_price=trade.hypothetical_price,
        rationale=trade.rationale,
        rationale_references=trade.rationale_references,
        expected_outcome=trade.expected_outcome,
        expected_horizon_days=trade.expected_horizon_days,
        proposed_at=trade.proposed_at,
        status=trade.status.value,
        review_note=trade.review_note,
        reviewed_at=trade.reviewed_at,
        closing_price=trade.closing_price,
    )


def _to_sample_response(
    sample: HypotheticalPerformanceSample,
) -> HypotheticalPerformanceSampleResponse:
    return HypotheticalPerformanceSampleResponse(
        sample_id=sample.sample_id,
        trade_id=sample.trade_id,
        observed_at=sample.observed_at,
        price=sample.price,
        gain_loss_percent=sample.gain_loss_percent,
    )


def _to_evaluation_response(
    evaluation: HypotheticalTradeEvaluation,
) -> HypotheticalTradeEvaluationResponse:
    return HypotheticalTradeEvaluationResponse(
        trade=_to_hypothetical_trade_response(evaluation.trade),
        latest_sample=(
            _to_sample_response(evaluation.latest_sample)
            if evaluation.latest_sample is not None
            else None
        ),
        gain_loss_percent=evaluation.gain_loss_percent,
        comparison_vs_no_action_percent=evaluation.comparison_vs_no_action_percent,
        thesis_direction_correct=evaluation.thesis_direction_correct,
        days_to_realize=evaluation.days_to_realize,
    )


@router.post("/hypothetical-trades", response_model=HypotheticalTradeResponse)
async def propose_hypothetical_trade(
    body: ProposeHypotheticalTradeRequest,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> HypotheticalTradeResponse:
    trade = await portfolio.propose_hypothetical_trade(
        body.user_id,
        symbol=body.symbol,
        action=HypotheticalTradeAction(body.action),
        quantity=body.quantity,
        rationale=body.rationale,
        expected_outcome=body.expected_outcome,
        expected_horizon_days=body.expected_horizon_days,
        rationale_references=body.rationale_references,
    )
    await session.commit()
    return _to_hypothetical_trade_response(trade)


@router.get("/hypothetical-trades", response_model=list[HypotheticalTradeResponse])
async def list_hypothetical_trades(
    user_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> list[HypotheticalTradeResponse]:
    trades = await portfolio.list_hypothetical_trades_for_user(user_id)
    return [_to_hypothetical_trade_response(t) for t in trades]


@router.get("/hypothetical-trades/{trade_id}", response_model=HypotheticalTradeEvaluationResponse)
async def get_hypothetical_trade_evaluation(
    trade_id: str, portfolio: PortfolioService = Depends(get_portfolio_service)
) -> HypotheticalTradeEvaluationResponse:
    evaluation = await portfolio.evaluate_hypothetical_trade(trade_id)
    return _to_evaluation_response(evaluation)


@router.post(
    "/hypothetical-trades/{trade_id}/samples", response_model=HypotheticalPerformanceSampleResponse
)
async def record_hypothetical_performance_sample(
    trade_id: str,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> HypotheticalPerformanceSampleResponse:
    sample = await portfolio.record_hypothetical_performance_sample(trade_id)
    await session.commit()
    return _to_sample_response(sample)


@router.post("/hypothetical-trades/{trade_id}/close", response_model=HypotheticalTradeResponse)
async def close_hypothetical_trade(
    trade_id: str,
    body: CloseHypotheticalTradeRequest,
    portfolio: PortfolioService = Depends(get_portfolio_service),
    session: AsyncSession = Depends(get_db_session),
) -> HypotheticalTradeResponse:
    trade = await portfolio.close_hypothetical_trade(trade_id, review_note=body.review_note)
    await session.commit()
    return _to_hypothetical_trade_response(trade)
