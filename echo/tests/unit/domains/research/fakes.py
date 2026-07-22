from __future__ import annotations

from typing import Any

from domains.research.schemas import (
    InsiderTransaction,
    Issuer,
    NewsArticle,
    NewsDigest,
    NewsFeedback,
    ProviderClaim,
    SecurityMasterEntry,
)


class FakeResearchRepository:
    def __init__(self) -> None:
        self.issuers: dict[str, Issuer] = {}
        self.securities: dict[tuple[str, str], SecurityMasterEntry] = {}
        self.claims: list[ProviderClaim] = []
        self.raw_responses: dict[str, dict[str, Any]] = {}
        self.articles: dict[str, NewsArticle] = {}
        self.digests: list[NewsDigest] = []
        self.feedback: list[NewsFeedback] = []
        self.insider_transactions: dict[str, InsiderTransaction] = {}

    async def save_issuer(self, issuer: Issuer) -> Issuer:
        self.issuers[issuer.issuer_id] = issuer
        return issuer

    async def get_issuer(self, issuer_id: str) -> Issuer | None:
        return self.issuers.get(issuer_id)

    async def get_issuer_by_cik(self, cik: str) -> Issuer | None:
        for issuer in self.issuers.values():
            if issuer.cik == cik:
                return issuer
        return None

    async def list_issuers_by_ticker(self, ticker: str) -> list[Issuer]:
        return [i for i in self.issuers.values() if i.primary_ticker == ticker]

    async def save_security(self, security: SecurityMasterEntry) -> SecurityMasterEntry:
        """Mirrors the real PostgresResearchRepository's upsert-by-
        (issuer_id, ticker) contract, preserving an existing row's stable
        security_id — same fidelity lesson as domains/portfolio's
        FakePortfolioRepository (Docs/DECISION_LOG.md's Phase 12 entry)."""
        key = (security.issuer_id, security.ticker)
        existing = self.securities.get(key)
        if existing is not None:
            security = security.model_copy(update={"security_id": existing.security_id})
        self.securities[key] = security
        return security

    async def list_securities_for_issuer(self, issuer_id: str) -> list[SecurityMasterEntry]:
        return [s for (iid, _), s in self.securities.items() if iid == issuer_id]

    async def save_claim(self, claim: ProviderClaim) -> None:
        self.claims.append(claim)

    async def list_claims_for_issuer(self, issuer_id: str) -> list[ProviderClaim]:
        return [c for c in self.claims if c.issuer_id == issuer_id]

    async def save_raw_response(
        self, raw_response_id: str, payload: dict[str, Any], now: Any
    ) -> None:
        self.raw_responses[raw_response_id] = payload

    async def save_articles(self, articles: list[NewsArticle]) -> None:
        for article in articles:
            self.articles[article.article_id] = article

    async def list_articles_for_issuer(self, issuer_id: str) -> list[NewsArticle]:
        return [a for a in self.articles.values() if a.issuer_id == issuer_id]

    async def save_digest(self, digest: NewsDigest) -> NewsDigest:
        self.digests.append(digest)
        return digest

    async def get_latest_digest(self, issuer_id: str) -> NewsDigest | None:
        matches = [d for d in self.digests if d.issuer_id == issuer_id]
        return matches[-1] if matches else None

    async def save_feedback(self, feedback: NewsFeedback) -> None:
        self.feedback.append(feedback)

    async def list_feedback_for_article(self, article_id: str) -> list[NewsFeedback]:
        return [f for f in self.feedback if f.article_id == article_id]

    async def save_insider_transactions(self, transactions: list[InsiderTransaction]) -> None:
        for transaction in transactions:
            self.insider_transactions[transaction.transaction_id] = transaction

    async def list_insider_transactions_for_issuer(
        self, issuer_id: str
    ) -> list[InsiderTransaction]:
        return [t for t in self.insider_transactions.values() if t.issuer_id == issuer_id]

    async def list_insider_transactions_for_insider(
        self, issuer_id: str, insider_cik: str
    ) -> list[InsiderTransaction]:
        return [
            t
            for t in self.insider_transactions.values()
            if t.issuer_id == issuer_id and t.insider_cik == insider_cik
        ]


class FakeFinnhubProvider:
    def __init__(self) -> None:
        self.response: dict[str, Any] = {}
        self.news_response: list[dict[str, Any]] = []
        self.raise_error: Exception | None = None
        self.calls: list[str] = []

    async def get_issuer_profile(self, ticker: str) -> dict[str, Any]:
        self.calls.append(ticker)
        if self.raise_error:
            raise self.raise_error
        return self.response

    async def get_company_news(
        self, ticker: str, *, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        self.calls.append(ticker)
        if self.raise_error:
            raise self.raise_error
        return self.news_response


class FakeSecEdgarProvider:
    def __init__(self) -> None:
        self.response: dict[str, Any] = {}
        self.raise_error: Exception | None = None
        self.calls: list[str] = []

    async def get_issuer_profile(self, ticker: str) -> dict[str, Any]:
        self.calls.append(ticker)
        if self.raise_error:
            raise self.raise_error
        return self.response


class FakeForm4Provider:
    def __init__(self) -> None:
        self.filings: list[dict[str, Any]] = []
        self.documents_by_accession: dict[str, dict[str, Any]] = {}
        self.raise_error: Exception | None = None
        self.calls: list[str] = []

    async def get_form4_filings(self, cik: str, *, limit: int = 20) -> list[dict[str, Any]]:
        self.calls.append(cik)
        if self.raise_error:
            raise self.raise_error
        return self.filings[:limit]

    async def get_form4_document(self, cik: str, accession_number: str) -> dict[str, Any]:
        self.calls.append(f"{cik}:{accession_number}")
        if self.raise_error:
            raise self.raise_error
        return self.documents_by_accession[accession_number]


class FakeSourceRecordRepository:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, record: Any) -> None:
        self.saved.append(record)

    async def get(self, record_id: str) -> Any:
        for record in self.saved:
            if record.record_id == record_id:
                return record
        return None


class FakeAuditRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        call_id = f"audit_fake_{len(self.recorded)}"
        self.recorded.append(
            {"audit_id": call_id, "action": action, "result": result, "detail": detail}
        )
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e.get("correlation_id") == correlation_id]
