"""Coordinates Email + Approvals for one write request — exactly what the
Application layer exists for (CONSTITUTION.md: "the only layer permitted to
coordinate more than one domain simultaneously"). Email writes always go
through the Approval Engine (Docs/APPROVAL_MODEL.md names Email as one of
its first two intended users, alongside Calendar) — this module is the only
place an email write proposal is created or executed; no domain-internal
shortcut exists. Mirrors application/orchestrators/calendar_writes.py's
structure exactly.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from email.message import EmailMessage as MimeMessage
from typing import Any

from core.errors import ValidationError
from domains.approvals.models import ProposalStatus, RiskLevel
from domains.approvals.schemas import ActionProposal
from domains.approvals.service import ApprovalService, WriteAdapter
from domains.email.service import EmailProviderPort, EmailService
from domains.email.write_adapters import (
    EmailArchiveVerifier,
    EmailArchiveWriteAdapter,
    EmailCreateDraftWriteAdapter,
    EmailDraftVerifier,
    EmailLabelVerifier,
    EmailLabelWriteAdapter,
    EmailReplyWriteAdapter,
    EmailSendVerifier,
    EmailSendWriteAdapter,
    EmailTrashVerifier,
    EmailTrashWriteAdapter,
    EmailUpdateDraftWriteAdapter,
)

_PROPOSAL_TTL = timedelta(hours=24)
_SCHEMA_VERSION = 1


def _build_raw_mime(
    *,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    """PROMPT.md Phase 21's payload always carries the fully-built MIME
    message rather than raw fields, matching
    application/orchestrators/calendar_writes.py's `_google_datetime`
    precedent of building the provider-shaped piece once at proposal time
    so domains/email/write_adapters.py never has to know about MIME
    encoding (Docs/APPROVAL_MODEL.md: "the immutable payload" is what gets
    approved and later executed — building it once here means the exact
    bytes a human reviewed are the exact bytes sent)."""
    message = MimeMessage()
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


class _CapturingWriteAdapter:
    """ApprovalService.execute() doesn't return the write adapter's raw
    result to its caller — wrapping the real adapter to capture the result
    lets the cache-sync step below see it, matching
    application/orchestrators/calendar_writes.py's identical
    `_CapturingWriteAdapter`."""

    def __init__(self, inner: WriteAdapter) -> None:
        self._inner = inner
        self.last_result: dict[str, Any] | None = None

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self._inner.execute(payload)
        self.last_result = result
        return result


class EmailWriteOrchestrator:
    def __init__(
        self, approvals: ApprovalService, email: EmailService, provider: EmailProviderPort
    ) -> None:
        self._approvals = approvals
        self._email = email
        self._provider = provider

    async def propose_create_draft(
        self, user_id: str, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> ActionProposal:
        payload = {
            "action": "create_draft",
            "raw_mime": _build_raw_mime(to=to, cc=cc, subject=subject, body=body),
        }
        return await self._propose(
            user_id,
            action_type="email.create_draft",
            risk_level=RiskLevel.LOW,
            summary=f"Create draft to {', '.join(to)}: {subject}",
            payload=payload,
        )

    async def propose_update_draft(
        self,
        user_id: str,
        *,
        draft_id: str,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> ActionProposal:
        payload = {
            "action": "update_draft",
            "draft_id": draft_id,
            "raw_mime": _build_raw_mime(to=to, cc=cc, subject=subject, body=body),
        }
        return await self._propose(
            user_id,
            action_type="email.update_draft",
            risk_level=RiskLevel.LOW,
            summary=f"Update draft {draft_id}: {subject}",
            payload=payload,
        )

    async def propose_send_message(
        self, user_id: str, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> ActionProposal:
        payload = {
            "action": "send_message",
            "raw_mime": _build_raw_mime(to=to, cc=cc, subject=subject, body=body),
        }
        return await self._propose(
            user_id,
            action_type="email.send_message",
            # Sending is externally visible to a real recipient and cannot
            # be un-sent — a deliberate, documented risk distinction from
            # the reversible draft/label/archive actions below.
            risk_level=RiskLevel.MEDIUM,
            summary=f"Send email to {', '.join(to)}: {subject}",
            payload=payload,
        )

    async def propose_reply(
        self, user_id: str, *, provider_message_id: str, body: str, to: list[str] | None = None
    ) -> ActionProposal:
        original = await self._email.get_message(user_id, provider_message_id=provider_message_id)
        recipients = to or [original.from_address]
        subject = (
            original.subject
            if original.subject.lower().startswith("re:")
            else f"Re: {original.subject}"
        )
        payload = {
            "action": "reply_message",
            "raw_mime": _build_raw_mime(
                to=recipients,
                subject=subject,
                body=body,
                in_reply_to=original.rfc_message_id,
                references=original.rfc_message_id,
            ),
            "thread_id": original.thread_id,
        }
        return await self._propose(
            user_id,
            action_type="email.reply_message",
            risk_level=RiskLevel.MEDIUM,
            summary=f"Reply to {', '.join(recipients)}: {subject}",
            payload=payload,
        )

    async def propose_archive(self, user_id: str, *, provider_message_id: str) -> ActionProposal:
        payload = {"action": "archive_message", "provider_message_id": provider_message_id}
        return await self._propose(
            user_id,
            action_type="email.archive_message",
            risk_level=RiskLevel.LOW,
            summary=f"Archive message {provider_message_id}",
            payload=payload,
        )

    async def propose_label(
        self,
        user_id: str,
        *,
        provider_message_id: str,
        add_label_ids: list[str] | None = None,
        remove_label_ids: list[str] | None = None,
    ) -> ActionProposal:
        add_label_ids = add_label_ids or []
        remove_label_ids = remove_label_ids or []
        if not add_label_ids and not remove_label_ids:
            raise ValidationError("label proposal requires at least one label to add or remove")
        payload = {
            "action": "label_message",
            "provider_message_id": provider_message_id,
            "add_label_ids": add_label_ids,
            "remove_label_ids": remove_label_ids,
        }
        return await self._propose(
            user_id,
            action_type="email.label_message",
            risk_level=RiskLevel.LOW,
            summary=f"Update labels on message {provider_message_id}",
            payload=payload,
        )

    async def propose_trash(self, user_id: str, *, provider_message_id: str) -> ActionProposal:
        payload = {"action": "trash_message", "provider_message_id": provider_message_id}
        return await self._propose(
            user_id,
            action_type="email.trash_message",
            # Recoverable within Gmail's own 30-day trash retention (verified
            # against Gmail's own documentation) but still a real mutating
            # action — matching Calendar's identical MEDIUM risk for delete.
            risk_level=RiskLevel.MEDIUM,
            summary=f"Move message {provider_message_id} to trash",
            payload=payload,
        )

    async def execute_proposal(self, proposal_id: str, user_id: str) -> ActionProposal:
        proposal = await self._approvals.get_proposal(proposal_id)
        access_token = await self._email.get_valid_access_token(user_id)

        write_adapter, verifier = self._build_adapter_and_verifier(
            proposal.action_type, proposal.payload, access_token
        )
        capturing = _CapturingWriteAdapter(write_adapter)
        executed = await self._approvals.execute(proposal_id, capturing, verifier)

        if executed.status == ProposalStatus.EXECUTED and capturing.last_result is not None:
            await self._sync_cache(user_id, executed.action_type, capturing.last_result)
        return executed

    async def _sync_cache(self, user_id: str, action_type: str, raw_result: dict[str, Any]) -> None:
        if action_type in ("email.create_draft", "email.update_draft"):
            # No dedicated list-drafts read capability exists yet (No
            # Future Scaffolding) — nothing reads a locally cached draft,
            # so there is nothing to keep in sync.
            return
        # Gmail's send/modify/trash responses don't necessarily include the
        # full `payload` (headers/subject) the way a `messages.get(format=
        # full)` response does — domains.email.policies.parse_message
        # degrades gracefully (falls back to "(no subject)"), and the next
        # real read refreshes it once the cache TTL expires. Matches
        # domains/calendar/service.py's identical cache_event pattern.
        await self._email.cache_message(user_id, raw_result)

    def _build_adapter_and_verifier(
        self, action_type: str, payload: dict[str, Any], access_token: str
    ) -> tuple[Any, Any]:
        if action_type == "email.create_draft":
            return (
                EmailCreateDraftWriteAdapter(self._provider, access_token),
                EmailDraftVerifier(self._provider, access_token),
            )
        if action_type == "email.update_draft":
            return (
                EmailUpdateDraftWriteAdapter(self._provider, access_token),
                EmailDraftVerifier(self._provider, access_token),
            )
        if action_type == "email.send_message":
            return (
                EmailSendWriteAdapter(self._provider, access_token),
                EmailSendVerifier(self._provider, access_token),
            )
        if action_type == "email.reply_message":
            return (
                EmailReplyWriteAdapter(self._provider, access_token),
                EmailSendVerifier(self._provider, access_token),
            )
        if action_type == "email.archive_message":
            return (
                EmailArchiveWriteAdapter(self._provider, access_token),
                EmailArchiveVerifier(self._provider, access_token),
            )
        if action_type == "email.label_message":
            return (
                EmailLabelWriteAdapter(self._provider, access_token),
                EmailLabelVerifier(
                    self._provider,
                    access_token,
                    payload.get("add_label_ids", []),
                    payload.get("remove_label_ids", []),
                ),
            )
        if action_type == "email.trash_message":
            return (
                EmailTrashWriteAdapter(self._provider, access_token),
                EmailTrashVerifier(self._provider, access_token),
            )
        raise ValidationError(f"unknown email action_type: {action_type!r}")

    async def _propose(
        self,
        user_id: str,
        *,
        action_type: str,
        risk_level: RiskLevel,
        summary: str,
        payload: dict[str, Any],
    ) -> ActionProposal:
        proposal = await self._approvals.propose(
            user_id=user_id,
            action_type=action_type,
            action_schema_version=_SCHEMA_VERSION,
            summary=summary,
            payload=payload,
            target_system="gmail",
            expected_effect=summary,
            risk_level=risk_level,
            required_permission="email.write",
            ttl=_PROPOSAL_TTL,
        )
        return await self._approvals.submit_for_approval(proposal.proposal_id)
