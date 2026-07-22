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

from sqlalchemy import Boolean, DateTime, Float, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from domains.research.schemas import (
    Chamber,
    CommitteeAssignment,
    EventType,
    FieldConflict,
    FilingContext,
    InsiderTransaction,
    Issuer,
    NewsArticle,
    NewsDigest,
    NewsFeedback,
    PoliticianOwner,
    PoliticianTransaction,
    PoliticianTransactionType,
    ProviderClaim,
    SecurityMasterEntry,
    TransactionType,
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


class InsiderTransactionRow(Base):
    __tablename__ = "research_insider_transactions"

    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer_id: Mapped[str] = mapped_column(String, index=True)
    insider_cik: Mapped[str] = mapped_column(String, index=True)
    insider_name: Mapped[str] = mapped_column(String)
    is_director: Mapped[bool] = mapped_column(Boolean)
    is_officer: Mapped[bool] = mapped_column(Boolean)
    is_ten_percent_owner: Mapped[bool] = mapped_column(Boolean)
    officer_title: Mapped[str | None] = mapped_column(String)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    transaction_code: Mapped[str] = mapped_column(String)
    transaction_type: Mapped[str] = mapped_column(String)
    shares: Mapped[float] = mapped_column(Float)
    price_per_share: Mapped[float | None] = mapped_column(Float)
    transaction_value: Mapped[float | None] = mapped_column(Float)
    acquired_disposed: Mapped[str] = mapped_column(String)
    shares_owned_after: Mapped[float | None] = mapped_column(Float)
    ownership_change_percent: Mapped[float | None] = mapped_column(Float)
    is_planned_sale: Mapped[bool] = mapped_column(Boolean, default=False)
    footnote_text: Mapped[str | None] = mapped_column(String)
    filing_context: Mapped[str | None] = mapped_column(String)
    filing_accession_number: Mapped[str] = mapped_column(String)
    source_record_id: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _row_to_insider_transaction(row: InsiderTransactionRow) -> InsiderTransaction:
    return InsiderTransaction(
        transaction_id=row.transaction_id,
        issuer_id=row.issuer_id,
        insider_cik=row.insider_cik,
        insider_name=row.insider_name,
        is_director=row.is_director,
        is_officer=row.is_officer,
        is_ten_percent_owner=row.is_ten_percent_owner,
        officer_title=row.officer_title,
        transaction_date=row.transaction_date,
        transaction_code=row.transaction_code,
        transaction_type=TransactionType(row.transaction_type),
        shares=row.shares,
        price_per_share=row.price_per_share,
        transaction_value=row.transaction_value,
        acquired_disposed=row.acquired_disposed,
        shares_owned_after=row.shares_owned_after,
        ownership_change_percent=row.ownership_change_percent,
        is_planned_sale=row.is_planned_sale,
        footnote_text=row.footnote_text,
        filing_context=FilingContext(row.filing_context) if row.filing_context else None,
        filing_accession_number=row.filing_accession_number,
        source_record_id=row.source_record_id,
        synced_at=row.synced_at,
    )


class PoliticianTransactionRow(Base):
    __tablename__ = "research_politician_transactions"

    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    politician_bioguide_id: Mapped[str | None] = mapped_column(String, index=True)
    politician_name: Mapped[str] = mapped_column(String)
    chamber: Mapped[str] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    party: Mapped[str | None] = mapped_column(String)
    report_id: Mapped[str] = mapped_column(String, index=True)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    owner: Mapped[str] = mapped_column(String)
    ticker: Mapped[str | None] = mapped_column(String, index=True)
    asset_name: Mapped[str] = mapped_column(String)
    asset_type: Mapped[str] = mapped_column(String)
    transaction_type: Mapped[str] = mapped_column(String)
    range_low: Mapped[float] = mapped_column(Float)
    range_high: Mapped[float | None] = mapped_column(Float)
    filing_delay_days: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String)
    source_record_id: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommitteeAssignmentRow(Base):
    """Primary key is the natural `(politician_bioguide_id,
    committee_thomas_id)` pair, not a synthetic id — this is a resynced
    snapshot (Docs/DECISION_LOG.md's Phase 19 entry), not an
    independently-lifecycled record, so there's no separate identity worth
    inventing beyond the membership relationship itself."""

    __tablename__ = "research_committee_assignments"

    politician_bioguide_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    committee_thomas_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    committee_name: Mapped[str] = mapped_column(String)
    chamber: Mapped[str] = mapped_column(String)
    jurisdiction_text: Mapped[str | None] = mapped_column(String)
    source_record_id: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _row_to_politician_transaction(row: PoliticianTransactionRow) -> PoliticianTransaction:
    return PoliticianTransaction(
        transaction_id=row.transaction_id,
        politician_bioguide_id=row.politician_bioguide_id,
        politician_name=row.politician_name,
        chamber=Chamber(row.chamber),
        state=row.state,
        party=row.party,
        report_id=row.report_id,
        filed_at=row.filed_at,
        transaction_date=row.transaction_date,
        owner=PoliticianOwner(row.owner),
        ticker=row.ticker,
        asset_name=row.asset_name,
        asset_type=row.asset_type,
        transaction_type=PoliticianTransactionType(row.transaction_type),
        range_low=row.range_low,
        range_high=row.range_high,
        filing_delay_days=row.filing_delay_days,
        comment=row.comment,
        source_record_id=row.source_record_id,
        synced_at=row.synced_at,
    )


def _row_to_committee_assignment(row: CommitteeAssignmentRow) -> CommitteeAssignment:
    return CommitteeAssignment(
        politician_bioguide_id=row.politician_bioguide_id,
        committee_thomas_id=row.committee_thomas_id,
        committee_name=row.committee_name,
        chamber=Chamber(row.chamber),
        jurisdiction_text=row.jurisdiction_text,
        source_record_id=row.source_record_id,
        synced_at=row.synced_at,
    )


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
    async def save_insider_transactions(self, transactions: list[InsiderTransaction]) -> None: ...
    async def list_insider_transactions_for_issuer(
        self, issuer_id: str
    ) -> list[InsiderTransaction]: ...
    async def list_insider_transactions_for_insider(
        self, issuer_id: str, insider_cik: str
    ) -> list[InsiderTransaction]: ...
    async def save_politician_transactions(
        self, transactions: list[PoliticianTransaction]
    ) -> None: ...
    async def list_politician_transactions_for_politician(
        self, politician_bioguide_id: str
    ) -> list[PoliticianTransaction]: ...
    async def list_politician_transactions_for_ticker(
        self, ticker: str
    ) -> list[PoliticianTransaction]: ...
    async def save_committee_assignments(
        self, assignments: list[CommitteeAssignment]
    ) -> None: ...
    async def list_committee_assignments_for_politician(
        self, politician_bioguide_id: str
    ) -> list[CommitteeAssignment]: ...


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

    async def save_insider_transactions(self, transactions: list[InsiderTransaction]) -> None:
        """Upsert by `transaction_id` — a transaction is re-saved once
        `filing_context` (Ollama's footnote classification) is filled in
        after the initial deterministic ingest, the same enrich-in-place
        pattern as `save_articles`."""
        for txn in transactions:
            row = await self._session.get(InsiderTransactionRow, txn.transaction_id)
            if row is None:
                row = InsiderTransactionRow(
                    transaction_id=txn.transaction_id, issuer_id=txn.issuer_id
                )
                self._session.add(row)
            row.insider_cik = txn.insider_cik
            row.insider_name = txn.insider_name
            row.is_director = txn.is_director
            row.is_officer = txn.is_officer
            row.is_ten_percent_owner = txn.is_ten_percent_owner
            row.officer_title = txn.officer_title
            row.transaction_date = txn.transaction_date
            row.transaction_code = txn.transaction_code
            row.transaction_type = txn.transaction_type.value
            row.shares = txn.shares
            row.price_per_share = txn.price_per_share
            row.transaction_value = txn.transaction_value
            row.acquired_disposed = txn.acquired_disposed
            row.shares_owned_after = txn.shares_owned_after
            row.ownership_change_percent = txn.ownership_change_percent
            row.is_planned_sale = txn.is_planned_sale
            row.footnote_text = txn.footnote_text
            row.filing_context = txn.filing_context.value if txn.filing_context else None
            row.filing_accession_number = txn.filing_accession_number
            row.source_record_id = txn.source_record_id
            row.synced_at = txn.synced_at
        await self._session.flush()

    async def list_insider_transactions_for_issuer(
        self, issuer_id: str
    ) -> list[InsiderTransaction]:
        result = await self._session.execute(
            select(InsiderTransactionRow).where(InsiderTransactionRow.issuer_id == issuer_id)
        )
        return [_row_to_insider_transaction(row) for row in result.scalars().all()]

    async def list_insider_transactions_for_insider(
        self, issuer_id: str, insider_cik: str
    ) -> list[InsiderTransaction]:
        result = await self._session.execute(
            select(InsiderTransactionRow).where(
                InsiderTransactionRow.issuer_id == issuer_id,
                InsiderTransactionRow.insider_cik == insider_cik,
            )
        )
        return [_row_to_insider_transaction(row) for row in result.scalars().all()]

    async def save_politician_transactions(self, transactions: list[PoliticianTransaction]) -> None:
        """Upsert by `transaction_id` — same enrich-in-place discipline as
        `save_insider_transactions`, load-bearing for the same reason
        (Docs/DECISION_LOG.md's Phase 18 entry): any re-sync re-fetches the
        same recent reports, and `parse_ptr_transactions` derives a
        deterministic `transaction_id`, so re-ingestion must resolve to the
        same rows."""
        for txn in transactions:
            row = await self._session.get(PoliticianTransactionRow, txn.transaction_id)
            if row is None:
                row = PoliticianTransactionRow(transaction_id=txn.transaction_id)
                self._session.add(row)
            row.politician_bioguide_id = txn.politician_bioguide_id
            row.politician_name = txn.politician_name
            row.chamber = txn.chamber.value
            row.state = txn.state
            row.party = txn.party
            row.report_id = txn.report_id
            row.filed_at = txn.filed_at
            row.transaction_date = txn.transaction_date
            row.owner = txn.owner.value
            row.ticker = txn.ticker
            row.asset_name = txn.asset_name
            row.asset_type = txn.asset_type
            row.transaction_type = txn.transaction_type.value
            row.range_low = txn.range_low
            row.range_high = txn.range_high
            row.filing_delay_days = txn.filing_delay_days
            row.comment = txn.comment
            row.source_record_id = txn.source_record_id
            row.synced_at = txn.synced_at
        await self._session.flush()

    async def list_politician_transactions_for_politician(
        self, politician_bioguide_id: str
    ) -> list[PoliticianTransaction]:
        result = await self._session.execute(
            select(PoliticianTransactionRow).where(
                PoliticianTransactionRow.politician_bioguide_id == politician_bioguide_id
            )
        )
        return [_row_to_politician_transaction(row) for row in result.scalars().all()]

    async def list_politician_transactions_for_ticker(
        self, ticker: str
    ) -> list[PoliticianTransaction]:
        result = await self._session.execute(
            select(PoliticianTransactionRow).where(PoliticianTransactionRow.ticker == ticker)
        )
        return [_row_to_politician_transaction(row) for row in result.scalars().all()]

    async def save_committee_assignments(self, assignments: list[CommitteeAssignment]) -> None:
        """Upsert by the natural `(politician_bioguide_id,
        committee_thomas_id)` key — re-syncing the reference dataset
        overwrites each politician's assignment rows in place rather than
        accumulating stale ones from a prior snapshot."""
        for assignment in assignments:
            row = await self._session.get(
                CommitteeAssignmentRow,
                (assignment.politician_bioguide_id, assignment.committee_thomas_id),
            )
            if row is None:
                row = CommitteeAssignmentRow(
                    politician_bioguide_id=assignment.politician_bioguide_id,
                    committee_thomas_id=assignment.committee_thomas_id,
                )
                self._session.add(row)
            row.committee_name = assignment.committee_name
            row.chamber = assignment.chamber.value
            row.jurisdiction_text = assignment.jurisdiction_text
            row.source_record_id = assignment.source_record_id
            row.synced_at = assignment.synced_at
        await self._session.flush()

    async def list_committee_assignments_for_politician(
        self, politician_bioguide_id: str
    ) -> list[CommitteeAssignment]:
        result = await self._session.execute(
            select(CommitteeAssignmentRow).where(
                CommitteeAssignmentRow.politician_bioguide_id == politician_bioguide_id
            )
        )
        return [_row_to_committee_assignment(row) for row in result.scalars().all()]
