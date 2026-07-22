"""API-boundary request/response schemas — never the domain's own
Issuer/ProviderClaim crossing the wire directly (CONSTITUTION.md: Typed
Contracts), matching apps/api/schemas/portfolio.py's convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FieldConflictResponse(BaseModel):
    field: str
    values_by_provider: dict[str, str]
    resolved_value: str
    resolved_from_provider: str


class IssuerResponse(BaseModel):
    issuer_id: str
    name: str
    cik: str | None
    primary_ticker: str | None
    industry: str | None
    source_record_ids: list[str]
    conflicts: list[FieldConflictResponse]
    created_at: datetime
    updated_at: datetime


class SecurityResponse(BaseModel):
    security_id: str
    issuer_id: str
    ticker: str
    exchange: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class ProviderClaimResponse(BaseModel):
    claim_id: str
    issuer_id: str
    provider: str
    ticker: str
    name: str | None
    cik: str | None
    industry: str | None
    retrieved_at: datetime


class EvidencePackageResponse(BaseModel):
    issuer: IssuerResponse
    securities: list[SecurityResponse]
    claims: list[ProviderClaimResponse]
    is_stale: bool
    generated_at: datetime


class NewsArticleResponse(BaseModel):
    article_id: str
    issuer_id: str
    headline: str
    blurb: str | None
    source: str
    url: str
    published_at: datetime
    cluster_id: str
    is_cluster_primary: bool
    event_type: str | None
    summary: str | None
    relevance_score: float | None
    synced_at: datetime


class NewsDigestResponse(BaseModel):
    digest_id: str
    issuer_id: str
    articles: list[NewsArticleResponse]
    narrative: str
    generated_at: datetime


class FeedbackRequest(BaseModel):
    user_id: str
    useful: bool


class FeedbackResponse(BaseModel):
    feedback_id: str
    article_id: str
    user_id: str
    useful: bool
    created_at: datetime


class InsiderTransactionResponse(BaseModel):
    transaction_id: str
    issuer_id: str
    insider_cik: str
    insider_name: str
    is_director: bool
    is_officer: bool
    is_ten_percent_owner: bool
    officer_title: str | None
    transaction_date: datetime
    transaction_code: str
    transaction_type: str
    shares: float
    price_per_share: float | None
    transaction_value: float | None
    acquired_disposed: str
    shares_owned_after: float | None
    ownership_change_percent: float | None
    is_planned_sale: bool
    footnote_text: str | None
    filing_context: str | None
    filing_accession_number: str
    synced_at: datetime


class InsiderProfileResponse(BaseModel):
    insider_cik: str
    insider_name: str
    issuer_id: str
    transaction_count: int
    total_purchased_value: float
    total_sold_value: float
    average_transaction_shares: float
    first_transaction_date: datetime
    last_transaction_date: datetime


class AnomalyFeatureResponse(BaseModel):
    feature_name: str
    value: float
    baseline_description: str
    is_notable: bool


class InsiderEvidenceResponse(BaseModel):
    issuer_id: str
    insider_cik: str
    transactions: list[InsiderTransactionResponse]
    profile: InsiderProfileResponse | None
    anomalies: list[AnomalyFeatureResponse]
    generated_at: datetime


class InsiderInterpretationResponse(BaseModel):
    issuer_id: str
    insider_cik: str
    interpretation: str


class PoliticianTransactionResponse(BaseModel):
    transaction_id: str
    politician_bioguide_id: str | None
    politician_name: str
    chamber: str
    state: str | None
    party: str | None
    report_id: str
    filed_at: datetime
    transaction_date: datetime
    owner: str
    ticker: str | None
    asset_name: str
    asset_type: str
    transaction_type: str
    range_low: float
    range_high: float | None
    filing_delay_days: int
    is_filing_late: bool
    comment: str | None
    synced_at: datetime


class PoliticianTradeProfileResponse(BaseModel):
    politician_bioguide_id: str
    politician_name: str
    transaction_count: int
    total_purchased_range_low: float
    total_purchased_range_high: float | None
    total_sold_range_low: float
    total_sold_range_high: float | None
    first_transaction_date: datetime
    last_transaction_date: datetime


class CommitteeAssignmentResponse(BaseModel):
    politician_bioguide_id: str
    committee_thomas_id: str
    committee_name: str
    chamber: str
    jurisdiction_text: str | None
    synced_at: datetime


class PoliticianEvidenceResponse(BaseModel):
    politician_bioguide_id: str
    transactions: list[PoliticianTransactionResponse]
    profile: PoliticianTradeProfileResponse | None
    committee_assignments: list[CommitteeAssignmentResponse]
    anomalies: list[AnomalyFeatureResponse]
    generated_at: datetime
