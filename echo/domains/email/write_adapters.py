"""Concrete `WriteAdapter`/`ExecutionVerifier` implementations
(domains/approvals/service.py's Protocols) for Email writes. Constructed
per-request by application/orchestrators/email_writes.py with one specific
user's already-resolved access token — never shared across users or cached
(PROMPT.md Phase 21 implement items 2/4/6/8/9/10/11: execution and
post-execution verification for draft/send/reply/archive/label/trash).

Payload shape (matching Docs/DECISION_LOG.md's Phase 11 convention for
Calendar): every proposal's `payload` dict always has `action`.
`create_draft`/`send_message`/`reply_message` additionally have `raw_mime`
(a base64url-encoded RFC 2822 message, built once by the orchestrator so
this module never has to know about MIME encoding); `update_draft`
additionally has `draft_id`; `reply_message` additionally has `thread_id`
(so Gmail keeps the reply in the original thread). `archive_message`/
`label_message`/`trash_message` additionally have `provider_message_id`,
and `label_message` additionally has `add_label_ids`/`remove_label_ids`.

Verification note: unlike domains/calendar/write_adapters.py (whose Google
Calendar behavior — e.g. a deleted event returning `status: "cancelled"`
rather than 404ing — was confirmed against a real, live-connected Google
account during Phase 11), the Gmail-specific behaviors this module assumes
(trashed messages remain gettable and carry a `TRASH` label; a sent message
carries a `SENT` label) are drawn from Gmail API's published documentation
only. Docs/DECISION_LOG.md's Phase 20-21 entry records this honestly as an
open item pending the user's own live Gmail OAuth connection
(CONSTITUTION.md Implementation Behavior Rule 2: "Never claim a provider
works without a successful test") — this code is not claimed "verified
live" the way Calendar's was.
"""

from __future__ import annotations

from typing import Any

from core.errors import EchoError
from domains.email.models import EmailLabel
from domains.email.service import EmailProviderPort


class EmailCreateDraftWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.create_draft(
            self._access_token, body={"message": {"raw": payload["raw_mime"]}}
        )


class EmailUpdateDraftWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.update_draft(
            self._access_token,
            draft_id=payload["draft_id"],
            body={"message": {"raw": payload["raw_mime"]}},
        )


class EmailSendWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.send_message(self._access_token, raw=payload["raw_mime"])


class EmailReplyWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.send_message(
            self._access_token, raw=payload["raw_mime"], thread_id=payload["thread_id"]
        )


class EmailArchiveWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.modify_labels(
            self._access_token,
            message_id=payload["provider_message_id"],
            add_label_ids=[],
            remove_label_ids=[EmailLabel.INBOX.value],
        )


class EmailLabelWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.modify_labels(
            self._access_token,
            message_id=payload["provider_message_id"],
            add_label_ids=payload.get("add_label_ids", []),
            remove_label_ids=payload.get("remove_label_ids", []),
        )


class EmailTrashWriteAdapter:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._provider.trash_message(
            self._access_token, message_id=payload["provider_message_id"]
        )


class EmailDraftVerifier:
    """Re-fetches the draft independently (a fresh read, not just trusting
    the write response) — matching CalendarWriteVerifier's identical
    reasoning."""

    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        draft_id = execution_result.get("id")
        if not draft_id:
            return False
        try:
            reloaded = await self._provider.get_draft(self._access_token, draft_id=draft_id)
        except EchoError:
            return False
        return bool(reloaded.get("id") == draft_id)


class EmailSendVerifier:
    """Docs/APPROVAL_MODEL.md's own Verification section names this exact
    check as its illustrative example: "confirming a Gmail message id and
    its sent state. A 200-level HTTP response from the provider is not
    sufficient evidence of success.\" """

    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        message_id = execution_result.get("id")
        if not message_id:
            return False
        try:
            reloaded = await self._provider.get_message(self._access_token, message_id=message_id)
        except EchoError:
            return False
        return reloaded.get("id") == message_id and "SENT" in reloaded.get("labelIds", [])


class EmailArchiveVerifier:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        message_id = execution_result.get("id")
        if not message_id:
            return False
        try:
            reloaded = await self._provider.get_message(self._access_token, message_id=message_id)
        except EchoError:
            return False
        return EmailLabel.INBOX.value not in reloaded.get("labelIds", [])


class EmailLabelVerifier:
    def __init__(
        self,
        provider: EmailProviderPort,
        access_token: str,
        add_label_ids: list[str],
        remove_label_ids: list[str],
    ) -> None:
        self._provider = provider
        self._access_token = access_token
        self._add_label_ids = add_label_ids
        self._remove_label_ids = remove_label_ids

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        message_id = execution_result.get("id")
        if not message_id:
            return False
        try:
            reloaded = await self._provider.get_message(self._access_token, message_id=message_id)
        except EchoError:
            return False
        labels = set(reloaded.get("labelIds", []))
        return all(label in labels for label in self._add_label_ids) and all(
            label not in labels for label in self._remove_label_ids
        )


class EmailTrashVerifier:
    def __init__(self, provider: EmailProviderPort, access_token: str) -> None:
        self._provider = provider
        self._access_token = access_token

    async def verify(self, execution_result: dict[str, Any], /) -> bool:
        message_id = execution_result.get("id")
        if not message_id:
            return False
        try:
            reloaded = await self._provider.get_message(self._access_token, message_id=message_id)
        except EchoError:
            return False
        return EmailLabel.TRASH.value in reloaded.get("labelIds", [])
