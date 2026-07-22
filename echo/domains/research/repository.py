"""Research owns its own persistence — issuers, securities, provider claims,
and raw responses are domain-owned aggregates (Docs/DOMAIN_OWNERSHIP.md:
"Research repositories own: security master, research documents, research
evidence..."), so the ORM tables live here rather than under
infrastructure/database/tables/ — matching the Portfolio/Calendar precedent.

`ResearchRawResponseRow` is the concrete storage the platform-wide
`core.provenance.SourceRecord.raw_storage_ref` points to, mirroring
domains/portfolio/repository.py's `SchwabRawResponseRow`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Boolean, DateTime, Float, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.research.schemas import (
    EventType,
    FieldConflict,
    Issuer,
    NewsArticle,
    NewsDigest,
    NewsFeedback,
    ProviderClaim,
    SecurityMasterEntry,
)
from infrastructure.database.base import Base


class IssuerRow(Base):
    __tablename__ = "research_issuers"

    issuer_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    cik: Mapped[str | None] = mapped_column(String, index=True, unique=True)
    primary_ticker: Mapped[str | None] = mapped_column(String, index=True)
    industry: Mapped[str | None] = mapped_column(String)
    source_record_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SecurityMasterEntryRow(Base):
    __tablename__ = "research_securities"

    security_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer_id: Mapped[str] = mapped_column(String, index=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    exchange: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_record_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderClaimRow(Base):
    __tablename__ = "research_provider_claims"

    claim_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer_id: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    ticker: Mapped[str] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    cik: Mapped[str | None] = mapped_column(String)
    industry: Mapped[str | None] = mapped_column(String)
    source_record_id: Mapped[str] = mapped_column(String)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResearchRawResponseRow(Base):
    __tablename__ = "research_raw_responses"

    raw_response_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NewsArticleRow(Base):
    __tablename__ = "research_news_articles"

    article_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer_id: Mapped[str] = mapped_column(String, index=True)
    headline: Mapped[str] = mapped_column(String)
    blurb: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_record_id: Mapped[str] = mapped_column(String)
    cluster_id: Mapped[str] = mapped_column(String, index=True)
    is_cluster_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    event_type: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(String)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NewsDigestRow(Base):
    __tablename__ = "research_news_digests"

    digest_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer_id: Mapped[str] = mapped_column(String, index=True)
    article_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    narrative: Mapped[str] = mapped_column(String)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NewsFeedbackRow(Base):
    __tablename__ = "research_news_feedback"

    feedback_id: Mapped[str] = mapped_column(String, primary_key=True)
    article_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    useful: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _row_to_article(row: NewsArticleRow) -> NewsArticle:
    return NewsArticle(
        article_id=row.article_id,
        issuer_id=row.issuer_id,
        headline=row.headline,
        blurb=row.blurb,
        source=row.source,
        url=row.url,
        published_at=row.published_at,
        source_record_id=row.source_record_id,
        cluster_id=row.cluster_id,
        is_cluster_primary=row.is_cluster_primary,
        event_type=EventType(row.event_type) if row.event_type else None,
        summary=row.summary,
        relevance_score=row.relevance_score,
        synced_at=row.synced_at,
    )


def _row_to_digest(row: NewsDigestRow) -> NewsDigest:
    return NewsDigest(
        digest_id=row.digest_id,
        issuer_id=row.issuer_id,
        article_ids=list(row.article_ids),
        narrative=row.narrative,
        generated_at=row.generated_at,
    )


def _row_to_feedback(row: NewsFeedbackRow) -> NewsFeedback:
    return NewsFeedback(
        feedback_id=row.feedback_id,
        article_id=row.article_id,
        user_id=row.user_id,
        useful=row.useful,
        created_at=row.created_at,
    )


def _row_to_issuer(row: IssuerRow) -> Issuer:
    return Issuer(
        issuer_id=row.issuer_id,
        name=row.name,
        cik=row.cik,
        primary_ticker=row.primary_ticker,
        industry=row.industry,
        source_record_ids=list(row.source_record_ids),
        conflicts=[FieldConflict(**c) for c in row.conflicts],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_security(row: SecurityMasterEntryRow) -> SecurityMasterEntry:
    return SecurityMasterEntry(
        security_id=row.security_id,
        issuer_id=row.issuer_id,
        ticker=row.ticker,
        exchange=row.exchange,
        active=row.active,
        source_record_ids=list(row.source_record_ids),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_claim(row: ProviderClaimRow) -> ProviderClaim:
    return ProviderClaim(
        claim_id=row.claim_id,
        issuer_id=row.issuer_id,
        provider=row.provider,
        ticker=row.ticker,
        name=row.name,
        cik=row.cik,
        industry=row.industry,
        source_record_id=row.source_record_id,
        retrieved_at=row.retrieved_at,
    )


class ResearchRepository(Protocol):
    async def save_issuer(self, issuer: Issuer) -> Issuer: ...
    async def get_issuer(self, issuer_id: str) -> Issuer | None: ...
    async def get_issuer_by_cik(self, cik: str) -> Issuer | None: ...
    async def list_issuers_by_ticker(self, ticker: str) -> list[Issuer]: ...
    async def save_security(self, security: SecurityMasterEntry) -> SecurityMasterEntry: ...
    async def list_securities_for_issuer(self, issuer_id: str) -> list[SecurityMasterEntry]: ...
    async def save_claim(self, claim: ProviderClaim) -> None: ...
    async def list_claims_for_issuer(self, issuer_id: str) -> list[ProviderClaim]: ...
    async def save_raw_response(
        self, raw_response_id: str, payload: dict[str, Any], now: datetime
    ) -> None: ...
    async def save_articles(self, articles: list[NewsArticle]) -> None: ...
    async def list_articles_for_issuer(self, issuer_id: str) -> list[NewsArticle]: ...
    async def save_digest(self, digest: NewsDigest) -> NewsDigest: ...
    async def get_latest_digest(self, issuer_id: str) -> NewsDigest | None: ...
    async def save_feedback(self, feedback: NewsFeedback) -> None: ...
    async def list_feedback_for_article(self, article_id: str) -> list[NewsFeedback]: ...


class PostgresResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_issuer(self, issuer: Issuer) -> Issuer:
        row = await self._session.get(IssuerRow, issuer.issuer_id)
        if row is None:
            row = IssuerRow(issuer_id=issuer.issuer_id, created_at=issuer.created_at)
            self._session.add(row)
        row.name = issuer.name
        row.cik = issuer.cik
        row.primary_ticker = issuer.primary_ticker
        row.industry = issuer.industry
        row.source_record_ids = issuer.source_record_ids
        row.conflicts = [c.model_dump(mode="json") for c in issuer.conflicts]
        row.updated_at = issuer.updated_at
        await self._session.flush()
        return issuer

    async def get_issuer(self, issuer_id: str) -> Issuer | None:
        row = await self._session.get(IssuerRow, issuer_id)
        return _row_to_issuer(row) if row is not None else None

    async def get_issuer_by_cik(self, cik: str) -> Issuer | None:
        result = await self._session.execute(select(IssuerRow).where(IssuerRow.cik == cik))
        row = result.scalar_one_or_none()
        return _row_to_issuer(row) if row is not None else None

    async def list_issuers_by_ticker(self, ticker: str) -> list[Issuer]:
        result = await self._session.execute(
            select(IssuerRow).where(IssuerRow.primary_ticker == ticker)
        )
        return [_row_to_issuer(row) for row in result.scalars().all()]

    async def save_security(self, security: SecurityMasterEntry) -> SecurityMasterEntry:
        result = await self._session.execute(
            select(SecurityMasterEntryRow).where(
                SecurityMasterEntryRow.issuer_id == security.issuer_id,
                SecurityMasterEntryRow.ticker == security.ticker,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            # A fresh security_id is correct here — this is genuinely a new
            # row, unlike the update branch below (Docs/DECISION_LOG.md's
            # Phase 12 entry: the account-upsert bug this mirrors and avoids
            # — an existing row must keep its own stable id, never adopt a
            # caller's freshly-generated one).
            row = SecurityMasterEntryRow(
                security_id=security.security_id,
                issuer_id=security.issuer_id,
                ticker=security.ticker,
                exchange=security.exchange,
                active=security.active,
                source_record_ids=security.source_record_ids,
                created_at=security.created_at,
                updated_at=security.updated_at,
            )
            self._session.add(row)
            await self._session.flush()
            return security
        row.exchange = security.exchange
        row.active = security.active
        row.source_record_ids = security.source_record_ids
        row.updated_at = security.updated_at
        await self._session.flush()
        return security.model_copy(update={"security_id": row.security_id})

    async def list_securities_for_issuer(self, issuer_id: str) -> list[SecurityMasterEntry]:
        result = await self._session.execute(
            select(SecurityMasterEntryRow).where(SecurityMasterEntryRow.issuer_id == issuer_id)
        )
        return [_row_to_security(row) for row in result.scalars().all()]

    async def save_claim(self, claim: ProviderClaim) -> None:
        self._session.add(
            ProviderClaimRow(
                claim_id=claim.claim_id,
                issuer_id=claim.issuer_id,
                provider=claim.provider,
                ticker=claim.ticker,
                name=claim.name,
                cik=claim.cik,
                industry=claim.industry,
                source_record_id=claim.source_record_id,
                retrieved_at=claim.retrieved_at,
            )
        )
        await self._session.flush()

    async def list_claims_for_issuer(self, issuer_id: str) -> list[ProviderClaim]:
        result = await self._session.execute(
            select(ProviderClaimRow).where(ProviderClaimRow.issuer_id == issuer_id)
        )
        return [_row_to_claim(row) for row in result.scalars().all()]

    async def save_raw_response(
        self, raw_response_id: str, payload: dict[str, Any], now: datetime
    ) -> None:
        self._session.add(
            ResearchRawResponseRow(raw_response_id=raw_response_id, payload=payload, created_at=now)
        )
        await self._session.flush()

    async def save_articles(self, articles: list[NewsArticle]) -> None:
        """Upsert by `article_id` — the same article row gets updated in
        place as it moves through the pipeline (ingested -> clustered ->
        classified -> scored), never re-inserted, so `list_articles_for_issuer`
        always reflects each article's latest, fully-enriched state."""
        for article in articles:
            row = await self._session.get(NewsArticleRow, article.article_id)
            if row is None:
                row = NewsArticleRow(article_id=article.article_id, issuer_id=article.issuer_id)
                self._session.add(row)
            row.headline = article.headline
            row.blurb = article.blurb
            row.source = article.source
            row.url = article.url
            row.published_at = article.published_at
            row.source_record_id = article.source_record_id
            row.cluster_id = article.cluster_id
            row.is_cluster_primary = article.is_cluster_primary
            row.event_type = article.event_type.value if article.event_type else None
            row.summary = article.summary
            row.relevance_score = article.relevance_score
            row.synced_at = article.synced_at
        await self._session.flush()

    async def list_articles_for_issuer(self, issuer_id: str) -> list[NewsArticle]:
        result = await self._session.execute(
            select(NewsArticleRow).where(NewsArticleRow.issuer_id == issuer_id)
        )
        return [_row_to_article(row) for row in result.scalars().all()]

    async def save_digest(self, digest: NewsDigest) -> NewsDigest:
        # Immutable (Docs/DATA_MODEL.md) — always an insert, never an
        # update, matching PortfolioSnapshot's precedent.
        self._session.add(
            NewsDigestRow(
                digest_id=digest.digest_id,
                issuer_id=digest.issuer_id,
                article_ids=digest.article_ids,
                narrative=digest.narrative,
                generated_at=digest.generated_at,
            )
        )
        await self._session.flush()
        return digest

    async def get_latest_digest(self, issuer_id: str) -> NewsDigest | None:
        result = await self._session.execute(
            select(NewsDigestRow)
            .where(NewsDigestRow.issuer_id == issuer_id)
            .order_by(NewsDigestRow.generated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _row_to_digest(row) if row is not None else None

    async def save_feedback(self, feedback: NewsFeedback) -> None:
        self._session.add(
            NewsFeedbackRow(
                feedback_id=feedback.feedback_id,
                article_id=feedback.article_id,
                user_id=feedback.user_id,
                useful=feedback.useful,
                created_at=feedback.created_at,
            )
        )
        await self._session.flush()

    async def list_feedback_for_article(self, article_id: str) -> list[NewsFeedback]:
        result = await self._session.execute(
            select(NewsFeedbackRow).where(NewsFeedbackRow.article_id == article_id)
        )
        return [_row_to_feedback(row) for row in result.scalars().all()]
