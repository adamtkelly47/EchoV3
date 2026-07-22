"""API-boundary response schemas for the unified dashboard (PROMPT.md
Phase 22) — never the Application layer's own `DashboardView` (application/
queries/dashboard_query.py) crossing the wire directly (CONSTITUTION.md:
Typed Contracts), matching every other apps/api/schemas/*.py convention.
Reuses the existing per-domain response schemas (`CalendarEventResponse`,
`ProposalResponse`, `MoneyDashboardResponse`) rather than redefining their
field lists — the same real data, the same shape, wherever it's shown.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from apps.api.schemas.approvals import ProposalResponse
from apps.api.schemas.calendar import CalendarEventResponse
from apps.api.schemas.portfolio import MoneyDashboardResponse

CardStatus = Literal["ok", "not_connected", "no_data", "not_available"]


class CardMetaResponse(BaseModel):
    status: CardStatus
    as_of: datetime | None
    detail: str | None


class TodayCardResponse(BaseModel):
    meta: CardMetaResponse
    events: list[CalendarEventResponse]


class MoneyCardResponse(BaseModel):
    meta: CardMetaResponse
    dashboard: MoneyDashboardResponse | None


class AttentionItemResponse(BaseModel):
    description: str
    severity: Literal["low", "medium", "high"]


class AttentionCardResponse(BaseModel):
    meta: CardMetaResponse
    items: list[AttentionItemResponse]


class ProjectsCardResponse(BaseModel):
    meta: CardMetaResponse


class RecentSessionResponse(BaseModel):
    session_id: str
    started_at: datetime
    status: str


class ConversationCardResponse(BaseModel):
    meta: CardMetaResponse
    recent_sessions: list[RecentSessionResponse]


class IntegrationEntryResponse(BaseModel):
    name: str
    connected: bool
    detail: str | None


class IntegrationStatusCardResponse(BaseModel):
    meta: CardMetaResponse
    integrations: list[IntegrationEntryResponse]


class ApprovalInboxCardResponse(BaseModel):
    meta: CardMetaResponse
    pending: list[ProposalResponse]


class DashboardResponse(BaseModel):
    user_id: str
    generated_at: datetime
    today: TodayCardResponse
    money: MoneyCardResponse
    attention: AttentionCardResponse
    projects: ProjectsCardResponse
    conversation: ConversationCardResponse
    integration_status: IntegrationStatusCardResponse
    approval_inbox: ApprovalInboxCardResponse
