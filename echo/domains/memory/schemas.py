"""Memory's own data contract (CONSTITUTION.md: Aggregate Ownership —
"MemoryRecord owns: confidence bounds / supersession rules / review
requirements."). No field list exists in Docs/DATA_MODEL.md to mirror (unlike
Approvals' APPROVAL_MODEL.md) — DATA_MODEL.md only maps Memory at the
ownership level, so this schema is derived directly from CONSTITUTION.md's
Memory Philosophy/Principles/Lifecycle sections and DOMAIN_OWNERSHIP.md's
Memory section.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.identifiers import new_id
from domains.memory.models import MemoryStatus


class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: new_id("memory"))
    user_id: str
    # A short, stable, normalized key identifying *what* this memory is
    # about (e.g. "user.favorite_color") — how supersession and conflict
    # detection find prior memories about the same subject without needing
    # semantic search (CONSTITUTION.md: Memory Principles).
    subject_key: str
    # The fact itself, stated in plain language.
    content: str
    status: MemoryStatus = MemoryStatus.CANDIDATE
    # CONSTITUTION.md: Memory Confidence — "Confidence shall never be
    # binary." Bounded [0.0, 1.0] by domains.memory.policies.
    confidence: float
    # Traceability (CONSTITUTION.md: Memory Principles — "reviewable /
    # traceable"; PROMPT.md Phase 9 verification: "source context remains
    # traceable"). Mirrors the source_type/source_id/correlation_id shape
    # already used for capability audit records.
    source_type: str
    source_id: str
    correlation_id: str | None = None
    # Set when this record was created to replace an older CONFIRMED record
    # (CONSTITUTION.md: Memory Lifecycle — Supersession).
    supersedes_memory_id: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None
    expires_at: datetime | None = None
