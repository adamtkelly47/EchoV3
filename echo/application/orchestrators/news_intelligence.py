"""News intelligence pipeline (PROMPT.md Phase 17) — event-type
classification and per-article summarization run against Ollama; the final
narrative synthesis runs against Claude, explicitly requested (never the
gateway's silent default) since it's the one step meant to produce prose a
user actually reads. Lives in application/orchestrators/ rather than inside
domains/research/ because it needs the Model Gateway (a cross-cutting
concern) and — for the portfolio-relevance boost (implement item 7) — a
second domain (Portfolio), both of which only the Application layer may
coordinate (CONSTITUTION.md: "the only layer permitted to coordinate more
than one domain simultaneously"), matching
application/orchestrators/memory_extraction.py's precedent for model-using
orchestration and Docs/DOMAIN_OWNERSHIP.md's Cross-Domain Interaction
Matrix (Portfolio-Research: Application Query only, never direct).

This is a single-user personal system (CONSTITUTION.md's Product
Definition) — `user_id` is threaded through only for consistency with every
other domain's own convention (Portfolio, Calendar), not because
`NewsDigest`/`NewsArticle` are actually per-user data. The portfolio-holding
relevance boost is computed for whichever `user_id` this run is invoked
with and baked into the shared, issuer-scoped result, the same way every
other domain in this codebase already treats `user_id` as a formality
ahead of a real multi-tenant Identity domain that doesn't exist yet.
"""

from __future__ import annotations

from pydantic import BaseModel

from application.model_gateway_factory import ModelGatewayPort
from core.errors import EchoError
from core.time import Clock
from domains.portfolio.service import PortfolioService
from domains.research.policies import (
    cluster_duplicates,
    compute_relevance_score,
    select_top_stories,
    suppress_low_relevance,
)
from domains.research.schemas import EventType, NewsArticle, NewsDigest
from domains.research.service import ResearchService
from providers.models.contracts import ModelRequest, Provider, TaskType


class _EventTypeClassification(BaseModel):
    event_type: EventType


class _SummaryOutput(BaseModel):
    summary: str


_CLASSIFY_PROMPT = (
    "Classify this news headline into exactly one category: earnings, "
    "merger_acquisition, leadership_change, regulatory, guidance, product, "
    "litigation, or other. Use ONLY the information given — do not assume "
    "facts not stated.\n\n"
    "Examples:\n"
    'Headline: "Apple beats Q3 earnings estimates" -> '
    '{{"event_type": "earnings"}}\n'
    'Headline: "Company X to acquire Company Y for $2B" -> '
    '{{"event_type": "merger_acquisition"}}\n'
    'Headline: "CEO steps down amid restructuring" -> '
    '{{"event_type": "leadership_change"}}\n'
    'Headline: "FDA approves new drug application" -> '
    '{{"event_type": "regulatory"}}\n'
    'Headline: "Company raises full-year guidance" -> '
    '{{"event_type": "guidance"}}\n'
    'Headline: "New product launch announced at event" -> '
    '{{"event_type": "product"}}\n'
    'Headline: "Company faces shareholder lawsuit" -> '
    '{{"event_type": "litigation"}}\n'
    'Headline: "Stock rises in afternoon trading" -> {{"event_type": "other"}}\n\n'
    "Now classify this headline. Reply with ONLY the JSON, nothing else.\n"
    'Headline: "{headline}"'
)

_SUMMARIZE_PROMPT = (
    "Summarize this news item in one or two sentences. Use ONLY the "
    "headline and blurb given below — never add outside information, "
    "context, or facts not present in the text.\n\n"
    'Headline: "{headline}"\n'
    'Blurb: "{blurb}"\n\n'
    "Reply with ONLY a JSON object of the exact form "
    '{{"summary": "<your one or two sentence summary>"}}, nothing else."'
)

_SYNTHESIS_PROMPT = (
    "You are writing a short news briefing for an investor about {company}. "
    "Below is a numbered list of recent, individually-verified news items "
    "about this company. Write a brief (3-5 sentence) narrative "
    "synthesizing what is happening, citing the specific item number in "
    "brackets (like [1]) after every claim you make. Do not state anything "
    "that is not directly supported by one of the numbered items below — "
    "every sentence must have at least one citation.\n\n"
    "{numbered_articles}"
)


class NewsIntelligenceOrchestrator:
    def __init__(
        self,
        research: ResearchService,
        portfolio: PortfolioService,
        gateway: ModelGatewayPort,
        clock: Clock,
    ) -> None:
        self._research = research
        self._portfolio = portfolio
        self._gateway = gateway
        self._clock = clock

    async def run_digest(
        self, issuer_id: str, ticker: str, company_name: str, user_id: str, *, top_n: int = 5
    ) -> NewsDigest:
        """PROMPT.md Phase 17 implement items 1-9 in one pipeline: ingest,
        cluster (implement item 4), classify (implement item 5), score
        (implement items 6-7), suppress low relevance (verification 2),
        summarize the survivors (implement item 8), then synthesize a
        narrative from the small, final top set (implement item 9)."""
        articles = await self._research.ingest_news(issuer_id, ticker)
        articles = cluster_duplicates(articles)

        is_holding = await self._is_portfolio_holding(ticker, user_id)
        now = self._clock.now_utc()
        scored: list[NewsArticle] = []
        for article in articles:
            if article.is_cluster_primary:
                event_type = await self._classify_event_type(article.headline)
                article = article.model_copy(update={"event_type": event_type})
            score = compute_relevance_score(article, is_portfolio_holding=is_holding, now=now)
            scored.append(article.model_copy(update={"relevance_score": score}))

        survivors = suppress_low_relevance(scored)
        top_stories = select_top_stories(survivors, limit=top_n)

        summarized: list[NewsArticle] = []
        for article in top_stories:
            summary = await self._summarize(article)
            summarized.append(article.model_copy(update={"summary": summary}))

        # Persist every scored article, not just the final top set — a
        # suppressed or non-primary article still exists and was still
        # evaluated; only the *digest* is meant to be small (PROMPT.md
        # Phase 17's own objective: "surface a small amount").
        top_ids = {a.article_id for a in summarized}
        non_top = [a for a in scored if a.article_id not in top_ids]
        await self._research.save_articles(summarized + non_top)

        narrative = await self._synthesize(company_name, summarized)
        digest = NewsDigest(
            issuer_id=issuer_id,
            article_ids=[a.article_id for a in summarized],
            narrative=narrative,
            generated_at=now,
        )
        return await self._research.save_digest(digest)

    async def _is_portfolio_holding(self, ticker: str, user_id: str) -> bool:
        try:
            dashboard = await self._portfolio.get_dashboard(user_id)
        except EchoError:
            return False  # no sync yet, or no credential — not a holding, not an error
        return any(w.symbol == ticker for w in dashboard.position_weights)

    async def _classify_event_type(self, headline: str) -> EventType:
        request = ModelRequest(
            task_type=TaskType.CLASSIFICATION,
            prompt=_CLASSIFY_PROMPT.format(headline=headline),
            temperature=0.0,
        )
        try:
            result = await self._gateway.generate_structured(request, _EventTypeClassification)
        except EchoError:
            return EventType.OTHER  # fail safe: no guess, not a wrong confident one
        return result.event_type

    async def _summarize(self, article: NewsArticle) -> str:
        request = ModelRequest(
            task_type=TaskType.SUMMARIZATION,
            prompt=_SUMMARIZE_PROMPT.format(
                headline=article.headline, blurb=article.blurb or article.headline
            ),
            temperature=0.0,
        )
        try:
            result = await self._gateway.generate_structured(request, _SummaryOutput)
        except EchoError:
            return article.headline  # fail safe: fall back to the headline, never invent
        return result.summary

    async def _synthesize(self, company_name: str, articles: list[NewsArticle]) -> str:
        if not articles:
            return f"No materially relevant news found for {company_name}."
        numbered = "\n".join(
            f"[{i + 1}] {a.headline} ({a.source}, {a.published_at.date().isoformat()}): "
            f"{a.summary or a.headline}"
            for i, a in enumerate(articles)
        )
        request = ModelRequest(
            task_type=TaskType.SYNTHESIS,
            prompt=_SYNTHESIS_PROMPT.format(company=company_name, numbered_articles=numbered),
            temperature=0.2,
        )
        try:
            response = await self._gateway.generate(request, provider=Provider.CLAUDE)
        except EchoError:
            return f"Synthesis unavailable — {len(articles)} relevant item(s) found."
        return response.output
