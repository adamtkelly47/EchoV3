"""The first Application-layer *query* (PROMPT.md Phase 22) — a read-only
cross-domain aggregation, not a workflow or a write. `application/queries/`
stays empty until something genuinely needs it (No Future Scaffolding);
this is that trigger. No single domain owns "the unified dashboard" — it
reads from Portfolio, Calendar, Approvals, and Conversation at once, which
is exactly the coordination CONSTITUTION.md reserves for the Application
layer ("the only layer permitted to coordinate more than one domain
simultaneously"), the same reason `NewsIntelligenceOrchestrator` and
`CalendarWriteOrchestrator` exist rather than wiring multiple domain
services directly into a route.

The "Projects" card (PROMPT.md Phase 22 implement item 4, Phase 23
implement item 10: "dashboard summary") reads real `ProjectService` data
as of Phase 23 — before that phase, no Projects domain existed at all, and
the card was a deliberately honest `not_available` placeholder rather than
a fabricated empty list pretending the domain was queried.

Every card carries its own `CardMeta` (`status` + `as_of`) — PROMPT.md
Phase 22 verification 2: "every card shows freshness or status." A domain
error (no credential, no synced snapshot, ...) is caught per-card and
turned into an honest status rather than failing the whole dashboard
response — one disconnected integration must never take down every other
card.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from core.config import Settings
from core.errors import EchoError
from core.time import Clock
from domains.approvals.schemas import ActionProposal
from domains.approvals.service import ApprovalService
from domains.calendar.schemas import CalendarEvent
from domains.calendar.service import CalendarService
from domains.conversation.schemas import ConversationSession
from domains.conversation.service import ConversationService
from domains.portfolio.schemas import MoneyDashboard
from domains.portfolio.service import PortfolioService
from domains.projects.models import ProjectStatus
from domains.projects.service import ProjectService

CardStatus = Literal["ok", "not_connected", "no_data", "not_available"]


class CardMeta(BaseModel):
    status: CardStatus
    as_of: datetime | None
    detail: str | None = None


class TodayCard(BaseModel):
    meta: CardMeta
    events: list[CalendarEvent]


class MoneyCard(BaseModel):
    meta: CardMeta
    dashboard: MoneyDashboard | None


class AttentionItem(BaseModel):
    description: str
    severity: Literal["low", "medium", "high"]


class AttentionCard(BaseModel):
    meta: CardMeta
    items: list[AttentionItem]


class ProjectSummaryEntry(BaseModel):
    project_id: str
    name: str
    status: str
    committed_tasks: int
    done_tasks: int
    total_tasks: int
    open_blockers: int


class ProjectsCard(BaseModel):
    meta: CardMeta
    projects: list[ProjectSummaryEntry]


class ConversationCard(BaseModel):
    meta: CardMeta
    recent_sessions: list[ConversationSession]


class IntegrationEntry(BaseModel):
    name: str
    connected: bool
    detail: str | None = None


class IntegrationStatusCard(BaseModel):
    meta: CardMeta
    integrations: list[IntegrationEntry]


class ApprovalInboxCard(BaseModel):
    meta: CardMeta
    pending: list[ActionProposal]


class DashboardView(BaseModel):
    user_id: str
    generated_at: datetime
    today: TodayCard
    money: MoneyCard
    attention: AttentionCard
    projects: ProjectsCard
    conversation: ConversationCard
    integration_status: IntegrationStatusCard
    approval_inbox: ApprovalInboxCard


class DashboardQueryService:
    def __init__(
        self,
        portfolio: PortfolioService,
        calendar: CalendarService,
        approvals: ApprovalService,
        conversations: ConversationService,
        projects: ProjectService,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._portfolio = portfolio
        self._calendar = calendar
        self._approvals = approvals
        self._conversations = conversations
        self._projects = projects
        self._clock = clock
        self._settings = settings

    async def build(self, user_id: str) -> DashboardView:
        now = self._clock.now_utc()
        approval_inbox = await self._build_approval_inbox(user_id, now)
        money = await self._build_money(user_id)
        return DashboardView(
            user_id=user_id,
            generated_at=now,
            today=await self._build_today(user_id, now),
            money=money,
            attention=await self._build_attention(user_id, now, approval_inbox),
            projects=await self._build_projects(user_id, now),
            conversation=await self._build_conversation(user_id),
            integration_status=await self._build_integration_status(user_id, now),
            approval_inbox=approval_inbox,
        )

    async def _build_today(self, user_id: str, now: datetime) -> TodayCard:
        if not await self._calendar.is_connected(user_id):
            return TodayCard(
                meta=CardMeta(
                    status="not_connected", as_of=None, detail="Google Calendar not connected"
                ),
                events=[],
            )
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        try:
            events = await self._calendar.list_events(
                user_id, calendar_id="primary", time_min=day_start, time_max=day_end
            )
        except EchoError as exc:
            return TodayCard(
                meta=CardMeta(status="not_connected", as_of=None, detail=str(exc)), events=[]
            )
        return TodayCard(meta=CardMeta(status="ok", as_of=now), events=events)

    async def _build_money(self, user_id: str) -> MoneyCard:
        if not await self._portfolio.is_connected(user_id):
            return MoneyCard(
                meta=CardMeta(status="not_connected", as_of=None, detail="Schwab not connected"),
                dashboard=None,
            )
        try:
            dashboard = await self._portfolio.get_dashboard(user_id)
        except EchoError as exc:
            return MoneyCard(
                meta=CardMeta(status="no_data", as_of=None, detail=str(exc)), dashboard=None
            )
        return MoneyCard(
            meta=CardMeta(status="ok", as_of=dashboard.last_verified_sync_at), dashboard=dashboard
        )

    async def _build_approval_inbox(self, user_id: str, now: datetime) -> ApprovalInboxCard:
        pending = await self._approvals.list_pending_for_user(user_id)
        return ApprovalInboxCard(meta=CardMeta(status="ok", as_of=now), pending=pending)

    async def _build_attention(
        self, user_id: str, now: datetime, approval_inbox: ApprovalInboxCard
    ) -> AttentionCard:
        """PROMPT.md Phase 22 implement item 3: "attention." Two concrete,
        already-computed real signals — pending approvals and IPS
        compliance breaches — not a speculative catch-all. Research-domain
        anomaly candidates (Phase 18/19) are not yet correlated against
        portfolio holdings here — a real, documented gap, not a fabricated
        signal."""
        items: list[AttentionItem] = []
        if approval_inbox.pending:
            items.append(
                AttentionItem(
                    description=f"{len(approval_inbox.pending)} action(s) awaiting your approval",
                    severity="medium",
                )
            )
        compliance = await self._portfolio.get_latest_compliance_result(user_id)
        if compliance is not None and not compliance.compliant:
            items.extend(
                AttentionItem(description=breach.description, severity="high")
                for breach in compliance.breaches
            )
        return AttentionCard(meta=CardMeta(status="ok", as_of=now), items=items)

    async def _build_projects(self, user_id: str, now: datetime) -> ProjectsCard:
        """PROMPT.md Phase 23 implement item 10: "dashboard summary." Only
        non-archived projects are surfaced — an archived project is
        deliberately no longer part of the active picture. Each entry's
        task/blocker counts come from `ProjectService.get_project_status_
        summary`'s own real, stored-fact computation (Phase 23 verification
        1), never re-derived here."""
        all_projects = await self._projects.list_projects_for_user(user_id)
        active = [p for p in all_projects if p.status != ProjectStatus.ARCHIVED]
        if not active:
            return ProjectsCard(meta=CardMeta(status="no_data", as_of=None), projects=[])
        entries = []
        for project in active:
            summary = await self._projects.get_project_status_summary(project.project_id)
            entries.append(
                ProjectSummaryEntry(
                    project_id=project.project_id,
                    name=project.name,
                    status=project.status.value,
                    committed_tasks=summary.committed_tasks,
                    done_tasks=summary.done_tasks,
                    total_tasks=summary.total_tasks,
                    open_blockers=summary.open_blockers,
                )
            )
        return ProjectsCard(meta=CardMeta(status="ok", as_of=now), projects=entries)

    async def _build_conversation(self, user_id: str) -> ConversationCard:
        sessions = await self._conversations.list_recent_sessions(user_id)
        status: CardStatus = "ok" if sessions else "no_data"
        as_of = sessions[0].started_at if sessions else None
        return ConversationCard(meta=CardMeta(status=status, as_of=as_of), recent_sessions=sessions)

    async def _build_integration_status(self, user_id: str, now: datetime) -> IntegrationStatusCard:
        """PROMPT.md Phase 22 implement item 6: "integration status." A
        credential/config-presence check, never a live health call to every
        external provider on each dashboard load (that cost would scale
        with every card render, not with real data change)."""
        entries = [
            IntegrationEntry(
                name="Google Calendar", connected=await self._calendar.is_connected(user_id)
            ),
            IntegrationEntry(name="Schwab", connected=await self._portfolio.is_connected(user_id)),
            IntegrationEntry(name="Finnhub", connected=bool(self._settings.finnhub_api_key)),
            IntegrationEntry(
                name="SEC EDGAR / Senate eFD",
                connected=bool(self._settings.research_contact_email),
                detail="shared fair-access contact email credential",
            ),
            IntegrationEntry(
                name="congress-legislators reference data",
                connected=True,
                detail="keyless, always available",
            ),
            IntegrationEntry(name="Claude", connected=bool(self._settings.anthropic_api_key)),
            IntegrationEntry(name="Ollama", connected=bool(self._settings.ollama_base_url)),
        ]
        return IntegrationStatusCard(meta=CardMeta(status="ok", as_of=now), integrations=entries)
