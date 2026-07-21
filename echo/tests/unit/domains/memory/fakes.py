from __future__ import annotations

from typing import Any

from domains.memory.schemas import MemoryRecord


class FakeAuditRepository:
    """Same shape as tests/unit/domains/approvals/fakes.py's fake — kept as
    its own copy per-domain rather than a shared test helper module, since
    no cross-domain test-utility package exists yet (No Future Scaffolding)."""

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


class FakeMemoryRepository:
    def __init__(self) -> None:
        self.records: dict[str, MemoryRecord] = {}

    async def save(self, record: MemoryRecord) -> None:
        self.records[record.memory_id] = record

    async def get(self, memory_id: str) -> MemoryRecord | None:
        return self.records.get(memory_id)

    async def list_for_user(self, user_id: str) -> list[MemoryRecord]:
        return [r for r in self.records.values() if r.user_id == user_id]

    async def list_for_subject(self, user_id: str, subject_key: str) -> list[MemoryRecord]:
        return [
            r
            for r in self.records.values()
            if r.user_id == user_id and r.subject_key == subject_key
        ]
