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
