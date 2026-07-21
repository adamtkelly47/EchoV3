"""API-boundary request/response schemas — never the domain's own
MemoryRecord crossing the wire directly (CONSTITUTION.md: Typed Contracts),
matching apps/api/schemas/conversations.py's convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ExtractMemoryRequest(BaseModel):
    user_id: str
    text: str
    source_type: str
    source_id: str


class SupersedeMemoryRequest(BaseModel):
    content: str
    confidence: float
    source_type: str
    source_id: str


class MemoryRecordResponse(BaseModel):
    memory_id: str
    user_id: str
    subject_key: str
    content: str
    status: str
    confidence: float
    source_type: str
    source_id: str
    correlation_id: str | None
    supersedes_memory_id: str | None
    created_at: datetime
    confirmed_at: datetime | None
    expires_at: datetime | None


class MemoryListResponse(BaseModel):
    memories: list[MemoryRecordResponse]
