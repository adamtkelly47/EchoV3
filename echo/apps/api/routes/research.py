"""No authentication/Identity domain exists yet — matching every other
routes module in this codebase, there is no per-user scoping here since
research data (unlike Portfolio/Calendar) isn't user-owned to begin with —
an Issuer is the same regardless of which user asks about it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.insider_intelligence import InsiderIntelligenceOrchestrator
from application.orchestrators.news_intelligence import NewsIntelligenceOrchestrator
from apps.api.dependencies import (
    get_db_session,
    get_insider_intelligence_orchestrator,
    get_news_intelligence_orchestrator,
    get_research_service,
)
from apps.api.schemas.research import (
    AnomalyFeatureResponse,
    EvidencePackageResponse,
    FeedbackRequest,
    FeedbackResponse,
    FieldConflictResponse,
    InsiderEvidenceResponse,
    InsiderInterpretationResponse,
    InsiderProfileResponse,
    InsiderTransactionResponse,
    IssuerResponse,
    NewsArticleResponse,
    NewsDigestResponse,
    ProviderClaimResponse,
    SecurityResponse,
)
from domains.research.schemas import (
    EvidencePackage,
    InsiderEvidenceView,
    Issuer,
    NewsArticle,
    NewsDigest,
)
from domains.research.service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


def _to_article_response(article: NewsArticle) -> NewsArticleResponse:
    return NewsArticleResponse(
        article_id=article.article_id,
        issuer_id=article.issuer_id,
        headline=article.headline,
        blurb=article.blurb,
        source=article.source,
        url=article.url,
        published_at=article.published_at,
        cluster_id=article.cluster_id,
        is_cluster_primary=article.is_cluster_primary,
        event_type=article.event_type.value if article.event_type else None,
        summary=article.summary,
        relevance_score=article.relevance_score,
        synced_at=article.synced_at,
    )


async def _to_digest_response(digest: NewsDigest, research: ResearchService) -> NewsDigestResponse:
    all_articles = await research.list_articles_for_issuer(digest.issuer_id)
    by_id = {a.article_id: a for a in all_articles}
    ordered = [by_id[aid] for aid in digest.article_ids if aid in by_id]
    return NewsDigestResponse(
        digest_id=digest.digest_id,
        issuer_id=digest.issuer_id,
        articles=[_to_article_response(a) for a in ordered],
        narrative=digest.narrative,
        generated_at=digest.generated_at,
    )


def _to_issuer_response(issuer: Issuer) -> IssuerResponse:
    return IssuerResponse(
        issuer_id=issuer.issuer_id,
        name=issuer.name,
        cik=issuer.cik,
        primary_ticker=issuer.primary_ticker,
        industry=issuer.industry,
        source_record_ids=issuer.source_record_ids,
        conflicts=[
            FieldConflictResponse(
                field=c.field,
                values_by_provider=c.values_by_provider,
                resolved_value=c.resolved_value,
                resolved_from_provider=c.resolved_from_provider,
            )
            for c in issuer.conflicts
        ],
        created_at=issuer.created_at,
        updated_at=issuer.updated_at,
    )


def _to_evidence_response(package: EvidencePackage) -> EvidencePackageResponse:
    return EvidencePackageResponse(
        issuer=_to_issuer_response(package.issuer),
        securities=[
            SecurityResponse(
                security_id=s.security_id,
                issuer_id=s.issuer_id,
                ticker=s.ticker,
                exchange=s.exchange,
                active=s.active,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in package.securities
        ],
        claims=[
            ProviderClaimResponse(
                claim_id=c.claim_id,
                issuer_id=c.issuer_id,
                provider=c.provider,
                ticker=c.ticker,
                name=c.name,
                cik=c.cik,
                industry=c.industry,
                retrieved_at=c.retrieved_at,
            )
            for c in package.claims
        ],
        is_stale=package.is_stale,
        generated_at=package.generated_at,
    )


def _to_insider_evidence_response(evidence: InsiderEvidenceView) -> InsiderEvidenceResponse:
    return InsiderEvidenceResponse(
        issuer_id=evidence.issuer_id,
        insider_cik=evidence.insider_cik,
        transactions=[
            InsiderTransactionResponse(
                transaction_id=t.transaction_id,
                issuer_id=t.issuer_id,
                insider_cik=t.insider_cik,
                insider_name=t.insider_name,
                is_director=t.is_director,
                is_officer=t.is_officer,
                is_ten_percent_owner=t.is_ten_percent_owner,
                officer_title=t.officer_title,
                transaction_date=t.transaction_date,
                transaction_code=t.transaction_code,
                transaction_type=t.transaction_type.value,
                shares=t.shares,
                price_per_share=t.price_per_share,
                transaction_value=t.transaction_value,
                acquired_disposed=t.acquired_disposed,
                shares_owned_after=t.shares_owned_after,
                ownership_change_percent=t.ownership_change_percent,
                is_planned_sale=t.is_planned_sale,
                footnote_text=t.footnote_text,
                filing_context=t.filing_context.value if t.filing_context else None,
                filing_accession_number=t.filing_accession_number,
                synced_at=t.synced_at,
            )
            for t in evidence.transactions
        ],
        profile=(
            InsiderProfileResponse(
                insider_cik=evidence.profile.insider_cik,
                insider_name=evidence.profile.insider_name,
                issuer_id=evidence.profile.issuer_id,
                transaction_count=evidence.profile.transaction_count,
                total_purchased_value=evidence.profile.total_purchased_value,
                total_sold_value=evidence.profile.total_sold_value,
                average_transaction_shares=evidence.profile.average_transaction_shares,
                first_transaction_date=evidence.profile.first_transaction_date,
                last_transaction_date=evidence.profile.last_transaction_date,
            )
            if evidence.profile is not None
            else None
        ),
        anomalies=[
            AnomalyFeatureResponse(
                feature_name=a.feature_name,
                value=a.value,
                baseline_description=a.baseline_description,
                is_notable=a.is_notable,
            )
            for a in evidence.anomalies
        ],
        generated_at=evidence.generated_at,
    )


@router.post("/issuers/sync", response_model=IssuerResponse)
async def sync_issuer(
    ticker: str,
    research: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db_session),
) -> IssuerResponse:
    issuer = await research.sync_issuer(ticker.upper())
    await session.commit()
    return _to_issuer_response(issuer)


@router.get("/issuers", response_model=IssuerResponse | None)
async def get_issuer_by_ticker(
    ticker: str, research: ResearchService = Depends(get_research_service)
) -> IssuerResponse | None:
    issuer = await research.get_issuer_by_ticker(ticker.upper())
    return _to_issuer_response(issuer) if issuer is not None else None


@router.get("/issuers/{issuer_id}/evidence", response_model=EvidencePackageResponse)
async def get_evidence_package(
    issuer_id: str, research: ResearchService = Depends(get_research_service)
) -> EvidencePackageResponse:
    package = await research.get_evidence_package(issuer_id)
    return _to_evidence_response(package)


@router.post("/issuers/{issuer_id}/news/digest", response_model=NewsDigestResponse)
async def run_news_digest(
    issuer_id: str,
    ticker: str,
    company_name: str,
    user_id: str,
    news: NewsIntelligenceOrchestrator = Depends(get_news_intelligence_orchestrator),
    research: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db_session),
) -> NewsDigestResponse:
    digest = await news.run_digest(issuer_id, ticker.upper(), company_name, user_id)
    await session.commit()
    return await _to_digest_response(digest, research)


@router.get("/issuers/{issuer_id}/news/digest", response_model=NewsDigestResponse)
async def get_latest_news_digest(
    issuer_id: str, research: ResearchService = Depends(get_research_service)
) -> NewsDigestResponse:
    digest = await research.get_latest_digest(issuer_id)
    return await _to_digest_response(digest, research)


@router.get("/issuers/{issuer_id}/news/articles", response_model=list[NewsArticleResponse])
async def list_news_articles(
    issuer_id: str, research: ResearchService = Depends(get_research_service)
) -> list[NewsArticleResponse]:
    articles = await research.list_articles_for_issuer(issuer_id)
    return [_to_article_response(a) for a in articles]


@router.post("/news/articles/{article_id}/feedback", response_model=FeedbackResponse)
async def record_news_feedback(
    article_id: str,
    body: FeedbackRequest,
    research: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    feedback = await research.record_feedback(article_id, body.user_id, body.useful)
    await session.commit()
    return FeedbackResponse(
        feedback_id=feedback.feedback_id,
        article_id=feedback.article_id,
        user_id=feedback.user_id,
        useful=feedback.useful,
        created_at=feedback.created_at,
    )


@router.post(
    "/issuers/{issuer_id}/insiders/ingest", response_model=list[InsiderTransactionResponse]
)
async def ingest_insider_transactions(
    issuer_id: str,
    cik: str,
    insider: InsiderIntelligenceOrchestrator = Depends(get_insider_intelligence_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> list[InsiderTransactionResponse]:
    transactions = await insider.ingest_and_classify(issuer_id, cik)
    await session.commit()
    return [
        InsiderTransactionResponse(
            transaction_id=t.transaction_id,
            issuer_id=t.issuer_id,
            insider_cik=t.insider_cik,
            insider_name=t.insider_name,
            is_director=t.is_director,
            is_officer=t.is_officer,
            is_ten_percent_owner=t.is_ten_percent_owner,
            officer_title=t.officer_title,
            transaction_date=t.transaction_date,
            transaction_code=t.transaction_code,
            transaction_type=t.transaction_type.value,
            shares=t.shares,
            price_per_share=t.price_per_share,
            transaction_value=t.transaction_value,
            acquired_disposed=t.acquired_disposed,
            shares_owned_after=t.shares_owned_after,
            ownership_change_percent=t.ownership_change_percent,
            is_planned_sale=t.is_planned_sale,
            footnote_text=t.footnote_text,
            filing_context=t.filing_context.value if t.filing_context else None,
            filing_accession_number=t.filing_accession_number,
            synced_at=t.synced_at,
        )
        for t in transactions
    ]


@router.get(
    "/issuers/{issuer_id}/insiders/{insider_cik}/evidence", response_model=InsiderEvidenceResponse
)
async def get_insider_evidence(
    issuer_id: str,
    insider_cik: str,
    research: ResearchService = Depends(get_research_service),
) -> InsiderEvidenceResponse:
    evidence = await research.get_insider_evidence(issuer_id, insider_cik)
    return _to_insider_evidence_response(evidence)


@router.post(
    "/issuers/{issuer_id}/insiders/{insider_cik}/interpret",
    response_model=InsiderInterpretationResponse,
)
async def interpret_insider_activity(
    issuer_id: str,
    insider_cik: str,
    company_name: str,
    insider: InsiderIntelligenceOrchestrator = Depends(get_insider_intelligence_orchestrator),
) -> InsiderInterpretationResponse:
    """Explicitly opt-in — a separate POST a user/client must call, never
    triggered as a side effect of ingestion or the evidence read
    (application/orchestrators/insider_intelligence.py's own docstring:
    Claude interpretation is "explicitly opt-in")."""
    interpretation = await insider.interpret(issuer_id, insider_cik, company_name)
    return InsiderInterpretationResponse(
        issuer_id=issuer_id, insider_cik=insider_cik, interpretation=interpretation
    )
