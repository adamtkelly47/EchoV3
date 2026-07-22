"""Insider transaction intelligence pipeline (PROMPT.md Phase 18). Footnote
context classification runs against Ollama; Claude interpretation is
explicitly opt-in — a separate method, never called automatically during
ingestion — matching PROMPT.md's own phrasing: "Claude interpretation
*when requested*." Lives in application/orchestrators/ rather than inside
domains/research/ because both stages need the Model Gateway, a
cross-cutting concern domains/ never imports (CONSTITUTION.md dependency
direction), matching news_intelligence.py's precedent.

The interpretation prompt is a direct application of Docs/CONSTITUTION.md's
"Verified Truth" section — "Echo must distinguish between: Verified facts.
Inferred conclusions. ... Every unsupported statement shall be identified as
unsupported" — and its Language Model Constraints: "Language models may
explain results. They may not define results." Claude is given verified
filing facts and deterministic, baseline-stated anomaly features
separately, told explicitly it may only explain what's already there, and
is forbidden from accusatory language — PROMPT.md Phase 18 verification 5
("Echo avoids unsupported accusations") is a direct instance of that
existing constitutional principle, not a new one invented for this phase.
"""

from __future__ import annotations

from pydantic import BaseModel

from application.model_gateway_factory import ModelGatewayPort
from core.errors import EchoError
from domains.research.schemas import FilingContext, InsiderEvidenceView, InsiderTransaction
from domains.research.service import ResearchService
from providers.models.contracts import ModelRequest, Provider, TaskType


class _FilingContextClassification(BaseModel):
    filing_context: FilingContext


_CLASSIFY_FOOTNOTE_PROMPT = (
    "Classify this SEC Form 4 filing footnote into exactly one category: "
    "routine_compensation, tax_withholding_explanation, gift_explanation, "
    "plan_10b5_1_explanation, or other_explanation. Use ONLY the footnote "
    "text given below — do not assume facts not stated.\n\n"
    "Examples:\n"
    'Footnote: "Represents shares granted as regular quarterly compensation '
    'for service as a director." -> {{"filing_context": "routine_compensation"}}\n'
    'Footnote: "Shares withheld to satisfy tax withholding obligations upon '
    'vesting." -> {{"filing_context": "tax_withholding_explanation"}}\n'
    'Footnote: "Gift of shares to a family trust." -> '
    '{{"filing_context": "gift_explanation"}}\n'
    'Footnote: "This transaction was effected pursuant to a Rule 10b5-1 '
    'trading plan adopted on March 1, 2026." -> '
    '{{"filing_context": "plan_10b5_1_explanation"}}\n\n'
    "Now classify this footnote. Reply with ONLY the JSON, nothing else.\n"
    'Footnote: "{footnote}"'
)

_INTERPRET_PROMPT = (
    "You are helping a user understand real SEC Form 4 insider transaction "
    "data for {insider_name} at {company_name}. Below are VERIFIED FACTS "
    "(directly from SEC filings) and COMPUTED FEATURES (deterministic "
    "calculations, each with its own comparison baseline stated).\n\n"
    "Your task: explain what these facts and features show, in plain "
    "language. You may describe patterns and context. You may NOT:\n"
    "- Assert that any transaction was illegal, improper, or evidence of "
    "wrongdoing\n"
    "- Use words like 'suspicious', 'illegal', 'insider trading', 'fraud', "
    "or similar accusatory language\n"
    "- State any conclusion not directly supported by the facts/features "
    "given below\n"
    "- Present a computed feature's baseline comparison as a fact about "
    "intent rather than what it actually is: a size or timing comparison\n\n"
    "If a feature is notable, explain what makes it notable using its own "
    "stated baseline — never invent a different baseline or a stronger "
    "claim than the feature itself supports.\n\n"
    "VERIFIED FACTS (transactions):\n{transactions_text}\n\n"
    "COMPUTED FEATURES (with stated baselines):\n{features_text}\n\n"
    "Write a brief (3-5 sentence) plain-language explanation."
)


class InsiderIntelligenceOrchestrator:
    def __init__(self, research: ResearchService, gateway: ModelGatewayPort) -> None:
        self._research = research
        self._gateway = gateway

    async def ingest_and_classify(
        self, issuer_id: str, cik: str, *, limit: int = 20
    ) -> list[InsiderTransaction]:
        """PROMPT.md Phase 18 implement item 8: "local filing context
        classification." Ingestion itself (items 1-5) stays inside
        `ResearchService.ingest_form4_transactions` — a pure, model-free
        pipeline; this orchestrator adds the one enrichment stage that
        needs Ollama, then persists the fully-enriched transactions.
        Transactions with no footnote text get `FilingContext.NO_FOOTNOTE`
        directly — real, deterministic, no model call needed for an
        absence."""
        transactions = await self._research.ingest_form4_transactions(issuer_id, cik, limit=limit)
        classified = []
        for txn in transactions:
            if not txn.footnote_text:
                classified.append(
                    txn.model_copy(update={"filing_context": FilingContext.NO_FOOTNOTE})
                )
                continue
            context = await self._classify_footnote(txn.footnote_text)
            classified.append(txn.model_copy(update={"filing_context": context}))
        await self._research.save_insider_transactions(classified)
        return classified

    async def interpret(self, issuer_id: str, insider_cik: str, company_name: str) -> str:
        """PROMPT.md Phase 18 implement item 10: "Claude interpretation
        when requested" — explicitly opt-in, never called automatically
        during `ingest_and_classify`."""
        evidence = await self._research.get_insider_evidence(issuer_id, insider_cik)
        return await self._synthesize_interpretation(evidence, company_name)

    async def _classify_footnote(self, footnote_text: str) -> FilingContext:
        request = ModelRequest(
            task_type=TaskType.CLASSIFICATION,
            prompt=_CLASSIFY_FOOTNOTE_PROMPT.format(footnote=footnote_text),
            temperature=0.0,
        )
        try:
            result = await self._gateway.generate_structured(request, _FilingContextClassification)
        except EchoError:
            return FilingContext.OTHER_EXPLANATION  # fail safe: no guess, a neutral bucket
        return result.filing_context

    async def _synthesize_interpretation(
        self, evidence: InsiderEvidenceView, company_name: str
    ) -> str:
        insider_name = evidence.transactions[0].insider_name if evidence.transactions else "unknown"
        transactions_text = "\n".join(
            f"- {t.transaction_date.date().isoformat()}: {t.transaction_type.value} of "
            f"{t.shares} shares"
            + (f" at ${t.price_per_share}/share" if t.price_per_share else "")
            + (f" (value ${t.transaction_value:,.2f})" if t.transaction_value else "")
            + (
                " — identified as a planned (Rule 10b5-1) sale per the filing"
                if t.is_planned_sale
                else ""
            )
            for t in evidence.transactions
        )
        features_text = (
            "\n".join(f"- {f.feature_name}: {f.baseline_description}" for f in evidence.anomalies)
            or "- none computed"
        )
        request = ModelRequest(
            task_type=TaskType.SYNTHESIS,
            prompt=_INTERPRET_PROMPT.format(
                insider_name=insider_name,
                company_name=company_name,
                transactions_text=transactions_text or "- none",
                features_text=features_text,
            ),
            temperature=0.2,
        )
        try:
            response = await self._gateway.generate(request, provider=Provider.CLAUDE)
        except EchoError:
            return (
                f"Interpretation unavailable — {len(evidence.transactions)} verified "
                "transaction(s) on record."
            )
        return response.output
