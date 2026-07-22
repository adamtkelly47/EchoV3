"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in query/body params, matching apps/api/routes/calendar.py's
identical documented convention for this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.email_intelligence import EmailIntelligenceOrchestrator
from application.orchestrators.email_writes import EmailWriteOrchestrator
from apps.api.dependencies import (
    get_db_session,
    get_email_intelligence_orchestrator,
    get_email_service,
    get_email_write_orchestrator,
)
from apps.api.schemas.approvals import ProposalResponse
from apps.api.schemas.email import (
    ConnectCallbackResponse,
    CreateDraftRequest,
    EmailAttachmentResponse,
    EmailMessageResponse,
    LabelRequest,
    MessageClassificationResponse,
    MessageListResponse,
    ReplyRequest,
    SendMessageRequest,
    ThreadSummaryResponse,
    UpdateDraftRequest,
)
from domains.approvals.schemas import ActionProposal
from domains.email.schemas import EmailMessage, MessageClassification
from domains.email.service import EmailService

router = APIRouter(prefix="/email", tags=["email"])


def _to_proposal_response(proposal: ActionProposal) -> ProposalResponse:
    return ProposalResponse(
        proposal_id=proposal.proposal_id,
        user_id=proposal.user_id,
        action_type=proposal.action_type,
        summary=proposal.summary,
        payload=proposal.payload,
        target_system=proposal.target_system,
        expected_effect=proposal.expected_effect,
        risk_level=proposal.risk_level.value,
        status=proposal.status.value,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        warnings=proposal.warnings,
    )


def _classification_response(
    classification: MessageClassification,
) -> MessageClassificationResponse:
    return MessageClassificationResponse(
        category=classification.category.value,
        needs_response=classification.needs_response,
        action_items=classification.action_items,
        classified_at=classification.classified_at,
    )


def _to_classification_response(
    classification: MessageClassification | None,
) -> MessageClassificationResponse | None:
    if classification is None:
        return None
    return _classification_response(classification)


def _to_response(message: EmailMessage) -> EmailMessageResponse:
    return EmailMessageResponse(
        provider_message_id=message.provider_message_id,
        thread_id=message.thread_id,
        subject=message.subject,
        snippet=message.snippet,
        from_address=message.from_address,
        to_addresses=message.to_addresses,
        date=message.date,
        label_ids=message.label_ids,
        is_unread=message.is_unread,
        attachments=[
            EmailAttachmentResponse(
                attachment_id=a.attachment_id,
                filename=a.filename,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
            )
            for a in message.attachments
        ],
        classification=_to_classification_response(message.classification),
        synced_at=message.synced_at,
    )


@router.get("/oauth/authorize")
async def authorize(
    user_id: str, email: EmailService = Depends(get_email_service)
) -> RedirectResponse:
    return RedirectResponse(email.start_authorization(user_id))


@router.get("/oauth/callback", response_model=ConnectCallbackResponse)
async def callback(
    code: str,
    state: str,
    email: EmailService = Depends(get_email_service),
    session: AsyncSession = Depends(get_db_session),
) -> ConnectCallbackResponse:
    credential = await email.complete_authorization(code, state)
    await session.commit()
    return ConnectCallbackResponse(user_id=credential.user_id, connected=True)


@router.get("/messages", response_model=MessageListResponse)
async def search_messages(
    user_id: str,
    query: str | None = None,
    max_results: int = 25,
    email: EmailService = Depends(get_email_service),
    session: AsyncSession = Depends(get_db_session),
) -> MessageListResponse:
    messages = await email.search_messages(user_id, query=query, max_results=max_results)
    await session.commit()
    return MessageListResponse(messages=[_to_response(m) for m in messages])


@router.get("/messages/{provider_message_id}", response_model=EmailMessageResponse)
async def get_message(
    provider_message_id: str,
    user_id: str,
    email: EmailService = Depends(get_email_service),
    session: AsyncSession = Depends(get_db_session),
) -> EmailMessageResponse:
    message = await email.get_message(user_id, provider_message_id=provider_message_id)
    await session.commit()
    return _to_response(message)


@router.get("/threads/{thread_id}", response_model=MessageListResponse)
async def get_thread(
    thread_id: str,
    user_id: str,
    email: EmailService = Depends(get_email_service),
    session: AsyncSession = Depends(get_db_session),
) -> MessageListResponse:
    messages = await email.get_thread(user_id, thread_id=thread_id)
    await session.commit()
    return MessageListResponse(messages=[_to_response(m) for m in messages])


@router.get("/threads/{thread_id}/summary", response_model=ThreadSummaryResponse)
async def summarize_thread(
    thread_id: str,
    user_id: str,
    intelligence: EmailIntelligenceOrchestrator = Depends(get_email_intelligence_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ThreadSummaryResponse:
    summary = await intelligence.summarize_thread(user_id, thread_id=thread_id)
    await session.commit()
    return ThreadSummaryResponse(thread_id=thread_id, summary=summary)


@router.post(
    "/messages/{provider_message_id}/classify", response_model=MessageClassificationResponse
)
async def classify_message(
    provider_message_id: str,
    user_id: str,
    intelligence: EmailIntelligenceOrchestrator = Depends(get_email_intelligence_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> MessageClassificationResponse:
    classification = await intelligence.classify_message(
        user_id, provider_message_id=provider_message_id
    )
    await session.commit()
    return _classification_response(classification)


@router.post("/drafts", response_model=ProposalResponse)
async def propose_create_draft(
    body: CreateDraftRequest,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_create_draft(
        body.user_id, to=body.to, subject=body.subject, body=body.body, cc=body.cc
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.patch("/drafts/{draft_id}", response_model=ProposalResponse)
async def propose_update_draft(
    draft_id: str,
    body: UpdateDraftRequest,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_update_draft(
        body.user_id,
        draft_id=draft_id,
        to=body.to,
        subject=body.subject,
        body=body.body,
        cc=body.cc,
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/messages/send", response_model=ProposalResponse)
async def propose_send_message(
    body: SendMessageRequest,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_send_message(
        body.user_id, to=body.to, subject=body.subject, body=body.body, cc=body.cc
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/messages/{provider_message_id}/reply", response_model=ProposalResponse)
async def propose_reply(
    provider_message_id: str,
    body: ReplyRequest,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_reply(
        body.user_id, provider_message_id=provider_message_id, body=body.body, to=body.to
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/messages/{provider_message_id}/archive", response_model=ProposalResponse)
async def propose_archive(
    provider_message_id: str,
    user_id: str,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_archive(user_id, provider_message_id=provider_message_id)
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/messages/{provider_message_id}/labels", response_model=ProposalResponse)
async def propose_label(
    provider_message_id: str,
    body: LabelRequest,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_label(
        body.user_id,
        provider_message_id=provider_message_id,
        add_label_ids=body.add_label_ids,
        remove_label_ids=body.remove_label_ids,
    )
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/messages/{provider_message_id}/trash", response_model=ProposalResponse)
async def propose_trash(
    provider_message_id: str,
    user_id: str,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.propose_trash(user_id, provider_message_id=provider_message_id)
    await session.commit()
    return _to_proposal_response(proposal)


@router.post("/proposals/{proposal_id}/execute", response_model=ProposalResponse)
async def execute_proposal(
    proposal_id: str,
    user_id: str,
    orchestrator: EmailWriteOrchestrator = Depends(get_email_write_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> ProposalResponse:
    proposal = await orchestrator.execute_proposal(proposal_id, user_id)
    await session.commit()
    return _to_proposal_response(proposal)
