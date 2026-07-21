"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in request bodies/query params, matching apps/api/routes/
conversations.py's documented convention for this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.memory_extraction import MemoryExtractionOrchestrator
from apps.api.dependencies import (
    get_db_session,
    get_memory_extraction_orchestrator,
    get_memory_service,
)
from apps.api.schemas.memory import (
    ExtractMemoryRequest,
    MemoryListResponse,
    MemoryRecordResponse,
    SupersedeMemoryRequest,
)
from core.observability import get_correlation_id
from domains.memory.schemas import MemoryRecord
from domains.memory.service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_response(record: MemoryRecord) -> MemoryRecordResponse:
    return MemoryRecordResponse(
        memory_id=record.memory_id,
        user_id=record.user_id,
        subject_key=record.subject_key,
        content=record.content,
        status=record.status.value,
        confidence=record.confidence,
        source_type=record.source_type,
        source_id=record.source_id,
        correlation_id=record.correlation_id,
        supersedes_memory_id=record.supersedes_memory_id,
        created_at=record.created_at,
        confirmed_at=record.confirmed_at,
        expires_at=record.expires_at,
    )


@router.post("/extract", response_model=MemoryListResponse)
async def extract(
    body: ExtractMemoryRequest,
    orchestrator: MemoryExtractionOrchestrator = Depends(get_memory_extraction_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryListResponse:
    records = await orchestrator.extract_and_record(
        body.text,
        user_id=body.user_id,
        source_type=body.source_type,
        source_id=body.source_id,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    return MemoryListResponse(memories=[_to_response(r) for r in records])


@router.post("/{memory_id}/confirm", response_model=MemoryRecordResponse)
async def confirm(
    memory_id: str,
    memory: MemoryService = Depends(get_memory_service),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRecordResponse:
    record = await memory.confirm(memory_id)
    await session.commit()
    return _to_response(record)


@router.post("/{memory_id}/supersede", response_model=MemoryRecordResponse)
async def supersede(
    memory_id: str,
    body: SupersedeMemoryRequest,
    memory: MemoryService = Depends(get_memory_service),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRecordResponse:
    record = await memory.supersede(
        memory_id,
        content=body.content,
        confidence=body.confidence,
        source_type=body.source_type,
        source_id=body.source_id,
        correlation_id=get_correlation_id(),
    )
    await session.commit()
    return _to_response(record)


@router.delete("/{memory_id}", response_model=MemoryRecordResponse)
async def delete(
    memory_id: str,
    memory: MemoryService = Depends(get_memory_service),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRecordResponse:
    record = await memory.delete(memory_id)
    await session.commit()
    return _to_response(record)


@router.get("/{memory_id}/conflicts", response_model=MemoryListResponse)
async def conflicts(
    memory_id: str,
    memory: MemoryService = Depends(get_memory_service),
) -> MemoryListResponse:
    record = await memory.get(memory_id)
    conflicting = await memory.detect_conflicts(record)
    return MemoryListResponse(memories=[_to_response(r) for r in conflicting])


@router.get("/search", response_model=MemoryListResponse)
async def search(
    user_id: str,
    query: str = "",
    memory: MemoryService = Depends(get_memory_service),
) -> MemoryListResponse:
    records = await memory.retrieve_active(user_id, query)
    return MemoryListResponse(memories=[_to_response(r) for r in records])


@router.get("", response_model=MemoryListResponse)
async def list_for_user(
    user_id: str,
    memory: MemoryService = Depends(get_memory_service),
) -> MemoryListResponse:
    records = await memory.list_all_for_user(user_id)
    return MemoryListResponse(memories=[_to_response(r) for r in records])
