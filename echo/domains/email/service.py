"""Email's aggregate-lifecycle owner. `EmailProviderPort` is defined here
(not in providers/), matching domains/calendar/service.py's identical
precedent: the domain owns the port, speaks to it in primitives (raw
dicts — Gmail's actual JSON responses), and does its own translation into
typed schemas (domains/email/policies.py) — so the concrete provider
adapter never needs to import anything from domains/
(scripts/check_architecture.py's providers-must-not-import-domains rule).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

from core.errors import EchoError
from core.identifiers import new_id
from core.time import Clock
from domains.email.errors import EmailCredentialNotFoundError, EmailTokenRefreshError
from domains.email.policies import (
    generate_oauth_state,
    is_stale,
    needs_refresh,
    parse_message,
    verify_oauth_state,
)
from domains.email.repository import EmailCredentialRepository, EmailMessageRepository
from domains.email.schemas import EmailCredential, EmailMessage, MessageClassification
from infrastructure.database.repositories.audit import AuditRepository
from infrastructure.secrets.encryption import SecretCipher

# How long a cached listing/message is trusted before a plain (non-search)
# read re-fetches from the provider (PROMPT.md Phase 20 implement item 8:
# email cache) — matching Calendar's identical Phase 10 TTL.
_CACHE_TTL = timedelta(minutes=5)


class EmailProviderPort(Protocol):
    async def exchange_code(self, code: str) -> dict[str, Any]: ...
    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]: ...
    async def list_messages(
        self, access_token: str, *, query: str | None = None, max_results: int = 25
    ) -> list[dict[str, Any]]: ...
    async def get_message(self, access_token: str, *, message_id: str) -> dict[str, Any]: ...
    async def get_thread(self, access_token: str, *, thread_id: str) -> dict[str, Any]: ...
    def build_authorization_url(self, state: str) -> str: ...
    async def create_draft(self, access_token: str, *, body: dict[str, Any]) -> dict[str, Any]: ...
    async def update_draft(
        self, access_token: str, *, draft_id: str, body: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def get_draft(self, access_token: str, *, draft_id: str) -> dict[str, Any]: ...
    async def send_message(
        self, access_token: str, *, raw: str, thread_id: str | None = None
    ) -> dict[str, Any]: ...
    async def modify_labels(
        self,
        access_token: str,
        *,
        message_id: str,
        add_label_ids: list[str],
        remove_label_ids: list[str],
    ) -> dict[str, Any]: ...
    async def trash_message(self, access_token: str, *, message_id: str) -> dict[str, Any]: ...


class EmailService:
    def __init__(
        self,
        credentials: EmailCredentialRepository,
        messages: EmailMessageRepository,
        provider: EmailProviderPort,
        cipher: SecretCipher,
        audit: AuditRepository,
        clock: Clock,
        state_secret: str,
    ) -> None:
        self._credentials = credentials
        self._messages = messages
        self._provider = provider
        self._cipher = cipher
        self._audit = audit
        self._clock = clock
        self._state_secret = state_secret

    def start_authorization(self, user_id: str) -> str:
        """Returns the full Google consent URL the user's browser should be
        sent to, embedding a signed, timestamped `state` (Docs/SECURITY.md:
        "Redirect target validation on OAuth callback flows")."""
        state = generate_oauth_state(user_id, new_id(), self._clock.now_utc(), self._state_secret)
        return self._provider.build_authorization_url(state)

    async def complete_authorization(self, code: str, state: str) -> EmailCredential:
        """Verifies `state` before ever exchanging `code` — a forged or
        replayed callback never reaches Google's token endpoint."""
        user_id = verify_oauth_state(state, self._state_secret, self._clock.now_utc())
        return await self.connect(user_id, code)

    async def connect(self, user_id: str, code: str) -> EmailCredential:
        """PROMPT.md Phase 20 implement items 1-2: OAuth, minimal read
        scopes (the scope actually granted comes back from Google itself,
        not assumed), token storage."""
        raw = await self._provider.exchange_code(code)
        now = self._clock.now_utc()
        credential = EmailCredential(
            user_id=user_id,
            encrypted_access_token=self._cipher.encrypt(raw["access_token"]),
            encrypted_refresh_token=self._cipher.encrypt(raw["refresh_token"]),
            access_token_expires_at=now + timedelta(seconds=raw["expires_in"]),
            scope=raw.get("scope", ""),
            created_at=now,
            updated_at=now,
        )
        await self._credentials.save(credential)
        await self._audit.record(action="email.connected", result="success", detail={"user_id": user_id})
        return credential

    async def is_connected(self, user_id: str) -> bool:
        """PROMPT.md Phase 22 pattern: "integration status." A credential
        existing is the real, honest signal available here — never a live
        provider health check on every dashboard load."""
        return await self._credentials.get_for_user(user_id) is not None

    async def search_messages(
        self,
        user_id: str,
        *,
        query: str | None = None,
        max_results: int = 25,
        force_refresh: bool = False,
    ) -> list[EmailMessage]:
        """Plain listing is cache-first (PROMPT.md Phase 20 implement item
        8). A text search always calls through — Gmail's own server-side
        relevance ranking for `q` can't be correctly reconstructed from a
        partial local cache (matching domains/calendar/service.py's
        identical reasoning for its own `query` parameter)."""
        if query is None and not force_refresh:
            cached = await self._messages.list_recent(user_id, limit=max_results)
            if cached and not is_stale(
                min(m.synced_at for m in cached), self._clock.now_utc(), _CACHE_TTL
            ):
                return cached

        access_token = await self.get_valid_access_token(user_id)
        raw_messages = await self._provider.list_messages(
            access_token, query=query, max_results=max_results
        )
        synced_at = self._clock.now_utc()
        messages = [parse_message(raw, user_id=user_id, synced_at=synced_at) for raw in raw_messages]
        if query is None:
            await self._messages.upsert_many(messages)
        return messages

    async def get_message(self, user_id: str, *, provider_message_id: str) -> EmailMessage:
        cached = await self._messages.get(user_id, provider_message_id)
        if cached is not None and not is_stale(cached.synced_at, self._clock.now_utc(), _CACHE_TTL):
            return cached

        access_token = await self.get_valid_access_token(user_id)
        raw = await self._provider.get_message(access_token, message_id=provider_message_id)
        message = parse_message(raw, user_id=user_id, synced_at=self._clock.now_utc())
        await self._messages.upsert_many([message])
        return message

    async def get_thread(self, user_id: str, *, thread_id: str) -> list[EmailMessage]:
        """PROMPT.md Phase 20 implement item 5: thread retrieval,
        cache-first the same way a single message read is."""
        cached = await self._messages.list_by_thread(user_id, thread_id)
        if cached and not is_stale(
            min(m.synced_at for m in cached), self._clock.now_utc(), _CACHE_TTL
        ):
            return cached

        access_token = await self.get_valid_access_token(user_id)
        raw_thread = await self._provider.get_thread(access_token, thread_id=thread_id)
        synced_at = self._clock.now_utc()
        messages = [
            parse_message(raw, user_id=user_id, synced_at=synced_at)
            for raw in raw_thread.get("messages", [])
        ]
        await self._messages.upsert_many(messages)
        return messages

    async def save_classification(
        self, user_id: str, provider_message_id: str, classification: MessageClassification
    ) -> None:
        """Used by application/orchestrators/email_intelligence.py after a
        local-model classification pass (PROMPT.md Phase 20 implement items
        9-11) — the domain never invokes the model gateway itself
        (CONSTITUTION.md: "the only layer permitted to coordinate more than
        one domain simultaneously" is Application, and the model gateway is
        a cross-cutting concern the domain layer never reaches for
        directly, matching application/orchestrators/news_intelligence.py's
        identical placement rationale)."""
        await self._messages.save_classification(user_id, provider_message_id, classification)

    async def cache_message(self, user_id: str, raw_message: dict[str, Any]) -> EmailMessage:
        """Phase 21: after a successful write (send/reply/label/archive/
        trash), the write path upserts the result into the same cache reads
        use, so a `search_messages` immediately after doesn't need to wait
        out `_CACHE_TTL` to see it — matching
        domains/calendar/service.py's `cache_event`."""
        message = parse_message(raw_message, user_id=user_id, synced_at=self._clock.now_utc())
        await self._messages.upsert_many([message])
        return message

    async def get_valid_access_token(self, user_id: str) -> str:
        """Public (Phase 21): domains/email/write_adapters.py's
        WriteAdapter/ExecutionVerifier implementations need a valid token
        the same way every read method here does — refresh-if-needed stays
        centralized in one place rather than duplicated."""
        credential = await self._credentials.get_for_user(user_id)
        if credential is None:
            raise EmailCredentialNotFoundError(f"no email connection for user {user_id!r}")

        now = self._clock.now_utc()
        if not needs_refresh(credential, now):
            return self._cipher.decrypt(credential.encrypted_access_token)

        refresh_token = self._cipher.decrypt(credential.encrypted_refresh_token)
        try:
            raw = await self._provider.refresh_access_token(refresh_token)
        except EchoError as exc:
            await self._audit.record(
                action="email.token_refresh_failed", result="failure", detail={"user_id": user_id}
            )
            raise EmailTokenRefreshError(f"could not refresh email token: {exc}") from exc

        updated = credential.model_copy(
            update={
                "encrypted_access_token": self._cipher.encrypt(raw["access_token"]),
                "access_token_expires_at": now + timedelta(seconds=raw["expires_in"]),
                "updated_at": now,
            }
        )
        await self._credentials.save(updated)
        await self._audit.record(
            action="email.token_refreshed", result="success", detail={"user_id": user_id}
        )
        return self._cipher.decrypt(updated.encrypted_access_token)
