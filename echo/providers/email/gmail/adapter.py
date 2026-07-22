"""Gmail adapter — plain httpx against Google's REST APIs, no
google-api-python-client/google-auth SDK dependency, matching
providers/calendar/google/adapter.py's identical precedent. Structurally
implements domains.email.service.EmailProviderPort (a Protocol, so no
import of domains/ is needed here — scripts/check_architecture.py's
providers-must-not-import-domains rule) by returning Gmail's raw JSON as
plain dicts; translation into typed domain objects happens in
domains/email/policies.py.

Endpoint URLs, request/response shapes, and scope semantics were verified
live against Google's own current API documentation before writing this
file (CONSTITUTION.md: Provider Due Diligence):
- OAuth: https://developers.google.com/identity/protocols/oauth2/web-server
- Scopes: https://developers.google.com/gmail/api/auth/scopes (gmail.modify
  is documented as "Read, compose, and send emails... does not allow
  immediate, permanent deletion of threads and messages, bypassing the
  trash" — i.e. it already covers read + compose + send + label + trash in
  one scope, so Phase 21 adds exactly one additional scope rather than
  stacking gmail.compose/gmail.send/gmail.labels separately.)
- Messages: https://developers.google.com/gmail/api/reference/rest/v1/users.messages
  (list/get/send/modify/trash)
- Drafts: https://developers.google.com/gmail/api/reference/rest/v1/users.drafts
  (create/update/get — a Draft resource is `{"id": ..., "message": {"raw": ...}}`)
- Sending: https://developers.google.com/gmail/api/guides/sending (`raw` is
  a base64url-encoded RFC 2822 message; replying within a thread requires
  a matching `Subject` plus `In-Reply-To`/`References` headers referencing
  the original message's `Message-Id` header, alongside the Gmail-specific
  `threadId` field on the send request)
- Trash retrieval: confirmed live (web search against Google's own current
  docs, 2026-07-22) that a trashed message remains retrievable via
  `messages.get` for up to 30 days (Gmail's own recovery-window behavior),
  matching this adapter's `EmailTrashVerifier` assumption.

Unlike domains/calendar/write_adapters.py's verifiers, this specific
end-to-end behavior has not been exercised against a real, authenticated
Gmail account from inside this codebase (Docs/DECISION_LOG.md's Phase 20-21
entry records this honestly) — only against Google's published
documentation, which is the most that's possible without the user's own
OAuth consent.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx

from core.errors import ProviderUnavailableError

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# bandit misreads "token" in the URL path as a hardcoded credential — this is
# Google's published OAuth token endpoint, a public URL, not a secret.
_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105
_GMAIL_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
_MESSAGES_URL = f"{_GMAIL_BASE_URL}/messages"
_DRAFTS_URL = f"{_GMAIL_BASE_URL}/drafts"

# Docs/SECURITY.md: "Read integrations ... request read-only scopes; write
# scopes are never requested until the corresponding write phase ... is
# reached" — Phase 21 is that write phase. `gmail.modify` is added
# alongside the existing gmail.readonly rather than replacing it, matching
# providers/calendar/google/adapter.py's identical additive-scope
# reasoning — a user who authorized under the old read-only-only grant must
# re-authorize; Google does not retroactively upgrade an existing grant's
# scope.
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
_REQUESTED_SCOPE = f"{READ_ONLY_SCOPE} {WRITE_SCOPE}"


class GmailAdapter:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": _REQUESTED_SCOPE,
            "access_type": "offline",  # required to receive a refresh_token
            "prompt": "consent",  # guarantees a refresh_token even on re-auth
            "state": state,
        }
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        return await self._post_form(
            _TOKEN_URL,
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._post_form(
            _TOKEN_URL,
            {
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            },
        )

    async def list_messages(
        self, access_token: str, *, query: str | None = None, max_results: int = 25
    ) -> list[dict[str, Any]]:
        """`messages.list` only returns `{id, threadId}` pairs — this
        fetches each one's full body so the returned list is already in the
        same "full message dict" shape `get_message` returns, matching
        domains.email.service.EmailProviderPort's contract that
        `list_messages` returns complete messages, not bare ids."""
        params: dict[str, Any] = {"maxResults": max_results}
        if query:
            params["q"] = query
        listing = await self._get(_MESSAGES_URL, access_token, params=params)
        refs: list[dict[str, Any]] = listing.get("messages", [])
        messages = []
        for ref in refs:
            messages.append(await self.get_message(access_token, message_id=ref["id"]))
        return messages

    async def get_message(self, access_token: str, *, message_id: str) -> dict[str, Any]:
        url = f"{_MESSAGES_URL}/{urllib.parse.quote(message_id, safe='')}"
        return await self._get(url, access_token, params={"format": "full"})

    async def get_thread(self, access_token: str, *, thread_id: str) -> dict[str, Any]:
        url = f"{_GMAIL_BASE_URL}/threads/{urllib.parse.quote(thread_id, safe='')}"
        return await self._get(url, access_token, params={"format": "full"})

    async def create_draft(self, access_token: str, *, body: dict[str, Any]) -> dict[str, Any]:
        return await self._post_json(_DRAFTS_URL, access_token, body)

    async def update_draft(
        self, access_token: str, *, draft_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{_DRAFTS_URL}/{urllib.parse.quote(draft_id, safe='')}"
        return await self._put_json(url, access_token, body)

    async def get_draft(self, access_token: str, *, draft_id: str) -> dict[str, Any]:
        url = f"{_DRAFTS_URL}/{urllib.parse.quote(draft_id, safe='')}"
        return await self._get(url, access_token)

    async def send_message(
        self, access_token: str, *, raw: str, thread_id: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"raw": raw}
        if thread_id:
            body["threadId"] = thread_id
        return await self._post_json(f"{_MESSAGES_URL}/send", access_token, body)

    async def modify_labels(
        self,
        access_token: str,
        *,
        message_id: str,
        add_label_ids: list[str],
        remove_label_ids: list[str],
    ) -> dict[str, Any]:
        url = f"{_MESSAGES_URL}/{urllib.parse.quote(message_id, safe='')}/modify"
        body = {"addLabelIds": add_label_ids, "removeLabelIds": remove_label_ids}
        return await self._post_json(url, access_token, body)

    async def trash_message(self, access_token: str, *, message_id: str) -> dict[str, Any]:
        url = f"{_MESSAGES_URL}/{urllib.parse.quote(message_id, safe='')}/trash"
        return await self._post_json(url, access_token, {})

    def _auth_header(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    async def _get(
        self, url: str, access_token: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    url, params=params, headers=self._auth_header(access_token)
                )
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Gmail request failed: {exc}") from exc

    async def _post_json(
        self, url: str, access_token: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=body, headers=self._auth_header(access_token))
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Gmail request failed: {exc}") from exc

    async def _put_json(self, url: str, access_token: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.put(url, json=body, headers=self._auth_header(access_token))
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Gmail request failed: {exc}") from exc

    async def _post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Google OAuth token request failed: {exc}") from exc
