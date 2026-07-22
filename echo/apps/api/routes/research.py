"""No authentication/Identity domain exists yet — matching every other
routes module in this codebase, there is no per-user scoping here since
research data (unlike Portfolio/Calendar) isn't user-owned to begin with —
an Issuer is the same regardless of which user asks about it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.news_intelligence import NewsIntelligenceOrchestrator
from apps.api.dependencies import (
    get_db_session,
    get_news_intelligence_orchestrator,
    get_research_service,
)
from apps.api.schemas.research import (
    EvidencePackageResponse,
    FeedbackRequest,
    FeedbackResponse,
    FieldConflictResponse,
    IssuerResponse,
    NewsArticleResponse,
    NewsDigestResponse,
    ProviderClaimResponse,
    SecurityResponse,
)
from domains.research.schemas import EvidencePackage, Issuer, NewsArticle, NewsDigest
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
