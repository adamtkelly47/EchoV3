"""No authentication/Identity domain exists yet (Phase 0's Identity domain
is unbuilt) — `user_id` is accepted directly in the request body for this
minimal slice. Real auth is a later phase's concern, not retrofitted here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
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
    ResponseChunkResponse,
    SendMessageRequest,
    StartConversationResponse,
)
from domains.conversation.events import ResponseChunkEvent
from domains.conversation.schemas import Channel
from domains.conversation.service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


class _RequestDisconnectSignal:
    """PROMPT.md Phase 26 implement item 4: "interruption handling
    contract." A real, already-available signal — no bespoke transport
    invented — a client (browser tab closed, voice channel hung up)
    disconnecting mid-stream is exactly an interruption. A future voice
    channel over a different transport (e.g. a WebSocket "stop speaking"
    message) would implement the same `InterruptSignal` Protocol
    differently, never a different contract."""

    def __init__(self, request: Request) -> None:
        self._request = request

    async def is_interrupted(self) -> bool:
        return await self._request.is_disconnected()


def _to_chunk_response(event: ResponseChunkEvent) -> ResponseChunkResponse:
    return ResponseChunkResponse(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        session_id=event.payload.session_id,
        text=event.payload.text,
        is_final=event.payload.is_final,
        interrupted=event.payload.interrupted,
    )


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
    message = await orchestrator.handle_message(
        session_id, body.content, channel=Channel(body.channel)
    )
    await session.commit()
    return MessageResponse(
        message_id=message.message_id,
        role=message.role.value,
        content=message.content,
        created_at=message.created_at,
        evidence=message.evidence,
        channel=message.channel.value,
        interrupted=message.interrupted,
    )


@router.post("/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    body: SendMessageRequest,
    request: Request,
    orchestrator: ConversationOrchestrator = Depends(get_conversation_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Newline-delimited JSON, one real `ResponseChunkEvent` per line
    (PROMPT.md Phase 26 implement item 3) — chat's own stream adopts the
    same typed contract a future voice channel will use, rather than
    voice inventing a new shape chat never had (this phase's objective:
    "without allowing voice logic to diverge from chat")."""
    interrupt = _RequestDisconnectSignal(request)

    async def event_stream() -> AsyncIterator[bytes]:
        async for event in orchestrator.handle_message_stream(
            session_id, body.content, channel=Channel(body.channel), interrupt=interrupt
        ):
            line = _to_chunk_response(event).model_dump_json()
            yield (line + "\n").encode("utf-8")
        await session.commit()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


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
                channel=m.channel.value,
                interrupted=m.interrupted,
            )
            for m in messages
        ],
    )
