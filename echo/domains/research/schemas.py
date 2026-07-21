"""Research's own data contracts (Docs/DOMAIN_OWNERSHIP.md: Research owns
"Company Profiles", "Security Master", "Tickers", "Identifiers", "Evidence
Provenance"). PROMPT.md Phase 16's objective is "provider independent
research storage" — `Issuer`/`SecurityMasterEntry` are the provider-agnostic,
merged view; `ProviderClaim` preserves exactly what each individual provider
said, so a disagreement between providers is never silently discarded
(verification 2: "source conflicts remain visible").
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.identifiers import new_id


class ProviderClaim(BaseModel):
    """What one provider said about one issuer, at one point in time —
    immutable once recorded (Docs/DATA_MODEL.md: Immutability). Never
    overwritten by a later claim from the same or a different provider;
    a new sync creates a new claim, matching PortfolioSnapshot's precedent
    of "new sync, new row" rather than mutating history."""

    claim_id: str = Field(default_factory=lambda: new_id("claim"))
    issuer_id: str
    provider: str
    ticker: str
    name: str | None = None
    cik: str | None = None
    industry: str | None = None
    source_record_id: str
    retrieved_at: datetime


class FieldConflict(BaseModel):
    """PROMPT.md Phase 16 verification 2: "source conflicts remain
    visible." Recorded whenever two providers' claims disagree on the same
    field for the same issuer — `resolved_value` is what
    `domains.research.policies.resolve_field`'s provider-priority rules
    chose, but every provider's own claimed value stays visible alongside
    it, not overwritten."""

    field: str
    values_by_provider: dict[str, str]
    resolved_value: str
    resolved_from_provider: str


class Issuer(BaseModel):
    """Echo's own stable representation of a real-world company —
    independent of any single provider's identifier scheme (PROMPT.md Phase
    16 implement item 2: "issuer identity"). `cik` is SEC's identifier, kept
    as a first-class field (not a generic identifier map) because it's the
    one cross-provider identifier this phase actually has and needs to
    query by — Docs/DECISION_LOG.md's Phase 16 entry explains why a generic
    identifiers dict was deliberately not built ahead of a second identifier
    type actually being needed (No Future Scaffolding)."""

    issuer_id: str = Field(default_factory=lambda: new_id("issuer"))
    name: str
    cik: str | None = None
    primary_ticker: str | None = None
    industry: str | None = None
    # Lineage (PROMPT.md Phase 16 verification 4: "every normalized item
    # retains source lineage") — every SourceRecord that ever contributed
    # to this issuer's current resolved field values.
    source_record_ids: list[str] = Field(default_factory=list)
    conflicts: list[FieldConflict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SecurityMasterEntry(BaseModel):
    """A specific tradable security belonging to an `Issuer` (PROMPT.md
    Phase 16 implement item 1: "security master") — kept distinct from
    `Issuer` per Docs/DOMAIN_OWNERSHIP.md's own separate listing of
    "Security Master" and "Company Profiles", since one issuer can in
    principle have more than one listed security (e.g. multiple share
    classes) even though this phase's real data has exactly one each."""

    security_id: str = Field(default_factory=lambda: new_id("security"))
    issuer_id: str
    ticker: str
    exchange: str | None = None
    active: bool = True
    source_record_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EvidencePackage(BaseModel):
    """PROMPT.md Phase 16 implement item 9: "evidence package generation" —
    "show your work" for any displayed research fact (CONSTITUTION.md:
    Provenance). Bundles the resolved `Issuer`, its securities, every raw
    `ProviderClaim` that contributed (so a conflict is visible in context,
    not just as an isolated `FieldConflict` list), and freshness."""

    issuer: Issuer
    securities: list[SecurityMasterEntry]
    claims: list[ProviderClaim]
    is_stale: bool
    generated_at: datetime
