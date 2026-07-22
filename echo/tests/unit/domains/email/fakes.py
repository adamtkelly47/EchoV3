from __future__ import annotations

from typing import Any

from domains.email.schemas import EmailCredential, EmailMessage, MessageClassification


class FakeEmailCredentialRepository:
    def __init__(self) -> None:
        self._store: dict[str, EmailCredential] = {}

    async def save(self, credential: EmailCredential) -> None:
        self._store[credential.user_id] = credential

    async def get_for_user(self, user_id: str) -> EmailCredential | None:
        return self._store.get(user_id)


class FakeEmailMessageRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], EmailMessage] = {}

    async def upsert_many(self, messages: list[EmailMessage]) -> None:
        for message in messages:
            self._by_key[(message.user_id, message.provider_message_id)] = message

    async def list_recent(self, user_id: str, *, limit: int = 25) -> list[EmailMessage]:
        matches = [m for m in self._by_key.values() if m.user_id == user_id]
        return sorted(matches, key=lambda m: m.date, reverse=True)[:limit]

    async def list_by_thread(self, user_id: str, thread_id: str) -> list[EmailMessage]:
        matches = [
            m for m in self._by_key.values() if m.user_id == user_id and m.thread_id == thread_id
        ]
        return sorted(matches, key=lambda m: m.date)

    async def get(self, user_id: str, provider_message_id: str) -> EmailMessage | None:
        return self._by_key.get((user_id, provider_message_id))

    async def save_classification(
        self, user_id: str, provider_message_id: str, classification: MessageClassification
    ) -> None:
        existing = self._by_key.get((user_id, provider_message_id))
        if existing is not None:
            self._by_key[(user_id, provider_message_id)] = existing.model_copy(
                update={"classification": classification}
            )


class FakeEmailProvider:
    """Configurable stand-in for EmailProviderPort — same shape as
    tests/unit/domains/calendar/fakes.py's FakeCalendarProvider."""

    def __init__(self) -> None:
        self.token_response: dict[str, Any] = {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
        }
        self.refresh_response: dict[str, Any] = {
            "access_token": "fake-refreshed-token",
            "expires_in": 3600,
        }
        self.list_messages_response: list[dict[str, Any]] = []
        self.get_message_response: dict[str, Any] = {}
        self.get_thread_response: dict[str, Any] = {"messages": []}
        self.create_draft_response: dict[str, Any] = {"id": "draft-1", "message": {"id": "msg-1"}}
        self.update_draft_response: dict[str, Any] = {"id": "draft-1", "message": {"id": "msg-1"}}
        self.get_draft_response: dict[str, Any] = {"id": "draft-1", "message": {"id": "msg-1"}}
        self.send_message_response: dict[str, Any] = {
            "id": "sent-1",
            "threadId": "thread-1",
            "labelIds": ["SENT"],
        }
        self.modify_labels_response: dict[str, Any] = {"id": "msg-1", "labelIds": []}
        self.trash_message_response: dict[str, Any] = {"id": "msg-1", "labelIds": ["TRASH"]}
        self.raise_on_refresh: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def build_authorization_url(self, state: str) -> str:
        self.calls.append(("build_authorization_url", {"state": state}))
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        self.calls.append(("exchange_code", {"code": code}))
        return self.token_response

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        self.calls.append(("refresh_access_token", {"refresh_token": refresh_token}))
        if self.raise_on_refresh:
            raise self.raise_on_refresh
        return self.refresh_response

    async def list_messages(
        self, access_token: str, *, query: str | None = None, max_results: int = 25
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "list_messages",
                {"access_token": access_token, "query": query, "max_results": max_results},
            )
        )
        return self.list_messages_response

    async def get_message(self, access_token: str, *, message_id: str) -> dict[str, Any]:
        self.calls.append(("get_message", {"access_token": access_token, "message_id": message_id}))
        return self.get_message_response

    async def get_thread(self, access_token: str, *, thread_id: str) -> dict[str, Any]:
        self.calls.append(("get_thread", {"access_token": access_token, "thread_id": thread_id}))
        return self.get_thread_response

    async def create_draft(self, access_token: str, *, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("create_draft", {"access_token": access_token, "body": body}))
        return self.create_draft_response

    async def update_draft(
        self, access_token: str, *, draft_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(
            ("update_draft", {"access_token": access_token, "draft_id": draft_id, "body": body})
        )
        return self.update_draft_response

    async def get_draft(self, access_token: str, *, draft_id: str) -> dict[str, Any]:
        self.calls.append(("get_draft", {"access_token": access_token, "draft_id": draft_id}))
        return self.get_draft_response

    async def send_message(
        self, access_token: str, *, raw: str, thread_id: str | None = None
    ) -> dict[str, Any]:
        self.calls.append(
            ("send_message", {"access_token": access_token, "raw": raw, "thread_id": thread_id})
        )
        return self.send_message_response

    async def modify_labels(
        self,
        access_token: str,
        *,
        message_id: str,
        add_label_ids: list[str],
        remove_label_ids: list[str],
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "modify_labels",
                {
                    "access_token": access_token,
                    "message_id": message_id,
                    "add_label_ids": add_label_ids,
                    "remove_label_ids": remove_label_ids,
                },
            )
        )
        return self.modify_labels_response

    async def trash_message(self, access_token: str, *, message_id: str) -> dict[str, Any]:
        self.calls.append(
            ("trash_message", {"access_token": access_token, "message_id": message_id})
        )
        return self.trash_message_response


class FakeAuditRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str | None = None,
        capability_id: str | None = None,
        provider: str | None = None,
        approval_id: str | None = None,
        verification_status: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        call_id = f"audit_fake_{len(self.recorded)}"
        self.recorded.append(
            {"audit_id": call_id, "action": action, "result": result, "detail": detail}
        )
        return call_id

    async def get(self, audit_id: str) -> Any:
        for entry in self.recorded:
            if entry["audit_id"] == audit_id:
                return entry
        return None

    async def list_for_correlation(self, correlation_id: str) -> list[Any]:
        return [e for e in self.recorded if e.get("correlation_id") == correlation_id]
