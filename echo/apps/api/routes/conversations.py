"""No authentication/Identity domain exists yet (Phase 0's Identity domain
is unbuilt) — `user_id` is accepted directly in the request body for this
minimal slice. Real auth is a later phase's concern, not retrofitted here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.conversation import ConversationOrchestrator
from apps.api.dependencies import (
    get_conversation_orchestrator,
    get_conversation_service,
    get_db_session,
)
from apps.api.schemas.conversations import (
    ConversationHistoryResponse,
    MessageResponse,
    SendMessageRequest,
    StartConversationResponse,
)
from domains.conversation.service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


class StartConversationRequest(BaseModel):
    user_id: str


@router.post("", response_model=StartConversationResponse)
async def start_conversation(
    body: StartConversationRequest,
    conversations: ConversationService = Depends(get_conversation_service),
    session: AsyncSession = Depends(get_db_session),
) -> StartConversationResponse:
    conversation = await conversations.start_session(body.user_id)
    await session.commit()
    return StartConversationResponse(
        session_id=conversation.session_id, started_at=conversation.started_at
    )


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    orchestrator: ConversationOrchestrator = Depends(get_conversation_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    message = await orchestrator.handle_message(session_id, body.content)
    await session.commit()
    return MessageResponse(
        message_id=message.message_id,
        role=message.role.value,
        content=message.content,
        created_at=message.created_at,
        evidence=message.evidence,
    )


@router.post("/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    body: SendMessageRequest,
    orchestrator: ConversationOrchestrator = Depends(get_conversation_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[bytes]:
        async for chunk in orchestrator.handle_message_stream(session_id, body.content):
            yield chunk.encode("utf-8")
        await session.commit()

    return StreamingResponse(event_stream(), media_type="text/plain")


@router.get("/{session_id}/messages", response_model=ConversationHistoryResponse)
async def get_history(
    session_id: str,
    conversations: ConversationService = Depends(get_conversation_service),
) -> ConversationHistoryResponse:
    messages = await conversations.get_history(session_id)
    return ConversationHistoryResponse(
        session_id=session_id,
        messages=[
            MessageResponse(
                message_id=m.message_id,
                role=m.role.value,
                content=m.content,
                created_at=m.created_at,
                evidence=m.evidence,
            )
            for m in messages
        ],
    )
