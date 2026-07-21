"""Research's aggregate-lifecycle owner. `ResearchProviderPort` is defined
here (not in providers/), matching domains/portfolio/service.py's
`PortfolioProviderPort` precedent: the domain owns the port, speaks to it in
primitives (raw dicts), and does its own translation into typed schemas
(domains/research/policies.py) — so a concrete provider adapter never needs
to import anything from domains/ (scripts/check_architecture.py's
providers-must-not-import-domains rule).

Multiple providers are registered simultaneously (unlike Calendar/Portfolio's
single provider each) — PROMPT.md Phase 16 verification 1: "two providers
can map into the same domain schema," and verification 3: "provider
replacement does not alter domain interfaces." Swapping which concrete
adapters back a given provider name never changes this Protocol's shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from core.identifiers import new_id
from core.provenance import SourceRecord, ValidationStatus
from core.time import Clock
from domains.research.errors import IssuerNotFoundError, NoProviderDataAvailableError
from domains.research.policies import (
    is_issuer_stale,
    parse_finnhub_issuer_claim,
    parse_sec_edgar_issuer_claim,
    resolve_issuer_fields,
)
from domains.research.repository import ResearchRepository
from domains.research.schemas import EvidencePackage, Issuer, ProviderClaim, SecurityMasterEntry
from infrastructure.database.repositories.audit import AuditRepository
from infrastructure.database.repositories.provenance import SourceRecordRepository


class ResearchProviderPort(Protocol):
    async def get_issuer_profile(self, ticker: str) -> dict[str, Any]: ...


class ResearchService:
    def __init__(
        self,
        research: ResearchRepository,
        source_records: SourceRecordRepository,
        providers: dict[str, ResearchProviderPort],
        audit: AuditRepository,
        clock: Clock,
    ) -> None:
        self._research = research
        self._source_records = source_records
        self._providers = providers
        self._audit = audit
        self._clock = clock

    async def sync_issuer(self, ticker: str) -> Issuer:
        """PROMPT.md Phase 16 implement items 3-8 in one pipeline: ingest
        from every configured provider, store raw responses and provenance,
        resolve entity identity (match-or-create), record each provider's
        claim, and re-resolve the issuer's fields from every claim on
        record. One provider failing doesn't block the others — recorded as
        a warning, not a hard failure (implement item 10: "provider
        fallback rules")."""
        now = self._clock.now_utc()
        warnings: list[str] = []
        # Two passes: every provider is fetched and parsed *before* entity
        # resolution runs, so identity resolution can prefer a CIK from
        # whichever provider supplied one — not just whichever provider
        # happened to be iterated first (dict order is an implementation
        # detail, not a resolution priority).
        parsed_by_provider: dict[str, tuple[dict[str, Any], str]] = {}
        for provider_name, provider in self._providers.items():
            try:
                raw = await provider.get_issuer_profile(ticker)
            except Exception as exc:  # noqa: BLE001 — one provider's failure must not abort the sync
                warnings.append(f"{provider_name} failed: {exc}")
                continue

            source_record_id = await self._store_raw_response(raw, provider=provider_name, now=now)
            if provider_name == "finnhub":
                parsed = parse_finnhub_issuer_claim(raw)
            elif provider_name == "sec_edgar":
                parsed = parse_sec_edgar_issuer_claim(raw, ticker=ticker)
            else:
                warnings.append(f"{provider_name}: no parser registered, skipped")
                continue
            parsed_by_provider[provider_name] = (parsed, source_record_id)

        if not parsed_by_provider:
            raise NoProviderDataAvailableError(
                f"no configured provider returned data for ticker {ticker!r} "
                f"(warnings: {'; '.join(warnings) if warnings else 'none'})"
            )

        cik_from_any_provider = next(
            (p["cik"] for p, _ in parsed_by_provider.values() if p.get("cik")), None
        )
        resolved_issuer_id = await self._resolve_issuer_id(cik_from_any_provider, ticker)

        for provider_name, (parsed, source_record_id) in parsed_by_provider.items():
            await self._research.save_claim(
                ProviderClaim(
                    issuer_id=resolved_issuer_id,
                    provider=provider_name,
                    ticker=parsed["ticker"],
                    name=parsed["name"],
                    cik=parsed["cik"],
                    industry=parsed["industry"],
                    source_record_id=source_record_id,
                    retrieved_at=now,
                )
            )

        all_claims = await self._research.list_claims_for_issuer(resolved_issuer_id)
        resolved_fields, conflicts = resolve_issuer_fields(all_claims)
        existing = await self._research.get_issuer(resolved_issuer_id)
        created_at = existing.created_at if existing is not None else now
        issuer = Issuer(
            issuer_id=resolved_issuer_id,
            name=resolved_fields["name"] or ticker,
            cik=resolved_fields["cik"],
            primary_ticker=ticker,
            industry=resolved_fields["industry"],
            source_record_ids=sorted({c.source_record_id for c in all_claims}),
            conflicts=conflicts,
            created_at=created_at,
            updated_at=now,
        )
        issuer = await self._research.save_issuer(issuer)

        security = SecurityMasterEntry(
            issuer_id=issuer.issuer_id,
            ticker=ticker,
            source_record_ids=issuer.source_record_ids,
            created_at=now,
            updated_at=now,
        )
        await self._research.save_security(security)

        await self._audit.record(
            action="research.issuer_synced",
            result="success",
            detail={
                "ticker": ticker,
                "issuer_id": issuer.issuer_id,
                "providers_reached": list(parsed_by_provider),
                "conflict_count": len(conflicts),
                "warnings": warnings,
            },
        )
        return issuer

    async def get_evidence_package(self, issuer_id: str) -> EvidencePackage:
        """PROMPT.md Phase 16 implement item 9. Never re-syncs — reads only
        what's already been ingested, mirroring domains/portfolio/service.py's
        get_dashboard()'s read/sync split."""
        issuer = await self._research.get_issuer(issuer_id)
        if issuer is None:
            raise IssuerNotFoundError(f"no issuer found for issuer_id {issuer_id!r}")
        securities = await self._research.list_securities_for_issuer(issuer_id)
        claims = await self._research.list_claims_for_issuer(issuer_id)
        now = self._clock.now_utc()
        return EvidencePackage(
            issuer=issuer,
            securities=securities,
            claims=claims,
            is_stale=is_issuer_stale(issuer.updated_at, now),
            generated_at=now,
        )

    async def get_issuer_by_ticker(self, ticker: str) -> Issuer | None:
        matches = await self._research.list_issuers_by_ticker(ticker)
        return matches[0] if matches else None

    async def _resolve_issuer_id(self, cik: str | None, ticker: str) -> str:
        """PROMPT.md Phase 16 implement item 7: "entity resolution."
        CIK is the one cross-provider identifier available this phase, so
        it's checked first (SEC.gov's cik.zfill(10) form is authoritative
        and stable); ticker is the fallback, since it's the only thing a
        provider without a CIK (e.g. Finnhub) can be matched by. Two
        providers reporting the same real company under different
        identifier schemes resolve to the same issuer regardless of which
        was ingested first (PROMPT.md Phase 16 verification 1)."""
        if cik is not None:
            existing = await self._research.get_issuer_by_cik(cik)
            if existing is not None:
                return existing.issuer_id
        matches = await self._research.list_issuers_by_ticker(ticker)
        if matches:
            return matches[0].issuer_id
        return new_id("issuer")

    async def _store_raw_response(
        self, raw: dict[str, Any], *, provider: str, now: datetime
    ) -> str:
        raw_response_id = new_id("researchraw")
        await self._research.save_raw_response(raw_response_id, raw, now)
        record = SourceRecord(
            source_type="research-api",
            provider=provider,
            retrieved_at=now,
            origin=f"{provider}-issuer-profile",
            raw_storage_ref=raw_response_id,
            parser_version="1",
            validation_status=ValidationStatus.PASSED,
        )
        await self._source_records.save(record)
        return record.record_id
