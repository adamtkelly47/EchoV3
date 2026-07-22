"""PROMPT.md Phase 22: the unified dashboard's single read endpoint. All
aggregation happens in `application/queries/dashboard_query.py`
(CONSTITUTION.md: the Application layer coordinates cross-domain reads) —
this module only maps that typed result onto the wire (verification 1:
"dashboard values come from backend APIs", verification 4: "no business
logic exists only in the frontend"). No authentication/Identity domain
exists yet — `user_id` is accepted directly in a query param, matching
every other routes module's documented convention for this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from application.queries.dashboard_query import (
    AttentionCard,
    CardMeta,
    ConversationCard,
    DashboardQueryService,
    DashboardView,
    IntegrationStatusCard,
    MoneyCard,
    ProjectsCard,
    TodayCard,
)
from apps.api.dependencies import get_dashboard_query_service
from apps.api.schemas.approvals import ProposalResponse
from apps.api.schemas.calendar import CalendarEventResponse
from apps.api.schemas.dashboard import (
    ApprovalInboxCardResponse,
    AttentionCardResponse,
    AttentionItemResponse,
    CardMetaResponse,
    ConversationCardResponse,
    DashboardResponse,
    IntegrationEntryResponse,
    IntegrationStatusCardResponse,
    MoneyCardResponse,
    ProjectsCardResponse,
    ProjectSummaryEntryResponse,
    RecentSessionResponse,
    TodayCardResponse,
)
from apps.api.schemas.portfolio import (
    AssetClassExposureResponse,
    ConcentrationWarningResponse,
    MoneyDashboardResponse,
    PositionGainLossResponse,
    PositionWeightResponse,
    SectorExposureResponse,
    SymbolExposureResponse,
)
from domains.approvals.schemas import ActionProposal
from domains.calendar.schemas import CalendarEvent

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _to_meta_response(meta: CardMeta) -> CardMetaResponse:
    return CardMetaResponse(status=meta.status, as_of=meta.as_of, detail=meta.detail)


def _to_calendar_event_response(event: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        event_id=event.event_id,
        provider_event_id=event.provider_event_id,
        calendar_id=event.calendar_id,
        summary=event.summary,
        description=event.description,
        start=event.start,
        end=event.end,
        all_day=event.all_day,
        timezone=event.timezone,
        status=event.status.value,
        is_busy=event.is_busy,
        recurring_event_id=event.recurring_event_id,
        html_link=event.html_link,
        synced_at=event.synced_at,
    )


def _to_today_response(card: TodayCard) -> TodayCardResponse:
    return TodayCardResponse(
        meta=_to_meta_response(card.meta),
        events=[_to_calendar_event_response(e) for e in card.events],
    )


def _to_money_response(card: MoneyCard) -> MoneyCardResponse:
    d = card.dashboard
    if d is None:
        return MoneyCardResponse(meta=_to_meta_response(card.meta), dashboard=None)
    return MoneyCardResponse(
        meta=_to_meta_response(card.meta),
        dashboard=MoneyDashboardResponse(
            user_id=d.user_id,
            generated_at=d.generated_at,
            last_verified_sync_at=d.last_verified_sync_at,
            is_stale=d.is_stale,
            total_market_value=d.total_market_value,
            reconciled=d.reconciled,
            position_weights=[
                PositionWeightResponse(
                    symbol=w.symbol,
                    account_id=w.account_id,
                    market_value=w.market_value,
                    weight_percent=w.weight_percent,
                )
                for w in d.position_weights
            ],
            asset_class_exposure=[
                AssetClassExposureResponse(
                    asset_type=e.asset_type.value,
                    market_value=e.market_value,
                    weight_percent=e.weight_percent,
                )
                for e in d.asset_class_exposure
            ],
            sector_exposure=[
                SectorExposureResponse(
                    sector=s.sector, market_value=s.market_value, weight_percent=s.weight_percent
                )
                for s in d.sector_exposure
            ],
            cross_account_exposure=[
                SymbolExposureResponse(
                    symbol=x.symbol,
                    total_quantity=x.total_quantity,
                    total_market_value=x.total_market_value,
                    account_ids=x.account_ids,
                )
                for x in d.cross_account_exposure
            ],
            concentration_warnings=[
                ConcentrationWarningResponse(
                    symbol=c.symbol,
                    weight_percent=c.weight_percent,
                    threshold_percent=c.threshold_percent,
                )
                for c in d.concentration_warnings
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
                for g in d.unrealized_gain_loss
            ],
            total_unrealized_gain_loss_dollar=d.total_unrealized_gain_loss_dollar,
            warnings=d.warnings,
            computed_value_record_id=d.computed_value_record_id,
        ),
    )


def _to_attention_response(card: AttentionCard) -> AttentionCardResponse:
    return AttentionCardResponse(
        meta=_to_meta_response(card.meta),
        items=[
            AttentionItemResponse(description=i.description, severity=i.severity)
            for i in card.items
        ],
    )


def _to_projects_response(card: ProjectsCard) -> ProjectsCardResponse:
    return ProjectsCardResponse(
        meta=_to_meta_response(card.meta),
        projects=[
            ProjectSummaryEntryResponse(
                project_id=p.project_id,
                name=p.name,
                status=p.status,
                committed_tasks=p.committed_tasks,
                done_tasks=p.done_tasks,
                total_tasks=p.total_tasks,
                open_blockers=p.open_blockers,
            )
            for p in card.projects
        ],
    )


def _to_conversation_response(card: ConversationCard) -> ConversationCardResponse:
    return ConversationCardResponse(
        meta=_to_meta_response(card.meta),
        recent_sessions=[
            RecentSessionResponse(session_id=s.session_id, started_at=s.started_at, status=s.status)
            for s in card.recent_sessions
        ],
    )


def _to_integration_status_response(card: IntegrationStatusCard) -> IntegrationStatusCardResponse:
    return IntegrationStatusCardResponse(
        meta=_to_meta_response(card.meta),
        integrations=[
            IntegrationEntryResponse(name=i.name, connected=i.connected, detail=i.detail)
            for i in card.integrations
        ],
    )


def _to_proposal_response(proposal: ActionProposal) -> ProposalResponse:
    return ProposalResponse(
        proposal_id=proposal.proposal_id,
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        summary=proposal.summary,
        payload=proposal.payload,
        target_system=proposal.target_system,
        expected_effect=proposal.expected_effect,
        risk_level=proposal.risk_level.value,
        status=proposal.status.value,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        warnings=proposal.warnings,
    )


def _to_dashboard_response(view: DashboardView) -> DashboardResponse:
    return DashboardResponse(
        user_id=view.user_id,
        generated_at=view.generated_at,
        today=_to_today_response(view.today),
        money=_to_money_response(view.money),
        attention=_to_attention_response(view.attention),
        projects=_to_projects_response(view.projects),
        conversation=_to_conversation_response(view.conversation),
        integration_status=_to_integration_status_response(view.integration_status),
        approval_inbox=ApprovalInboxCardResponse(
            meta=_to_meta_response(view.approval_inbox.meta),
            pending=[_to_proposal_response(p) for p in view.approval_inbox.pending],
        ),
    )


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    user_id: str, dashboard: DashboardQueryService = Depends(get_dashboard_query_service)
) -> DashboardResponse:
    view = await dashboard.build(user_id)
    return _to_dashboard_response(view)
