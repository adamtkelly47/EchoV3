"""No authentication/Identity domain exists yet — matching every other
routes module in this codebase, there is no per-user scoping here since
research data (unlike Portfolio/Calendar) isn't user-owned to begin with —
an Issuer is the same regardless of which user asks about it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session, get_research_service
from apps.api.schemas.research import (
    EvidencePackageResponse,
    FieldConflictResponse,
    IssuerResponse,
    ProviderClaimResponse,
    SecurityResponse,
)
from domains.research.schemas import EvidencePackage, Issuer
from domains.research.service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


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
