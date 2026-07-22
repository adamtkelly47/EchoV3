"""PROMPT.md Phase 26 implement item 4: "interruption handling contract."
Conversation defines the shape any caller must satisfy to signal an
in-progress interruption — it never implements one itself, matching
`domains/approvals/service.py`'s `WriteAdapter`/`ExecutionVerifier`
precedent of a domain-owned Protocol the caller (here, `apps/api/routes/
conversations.py`) supplies a concrete instance of. A real HTTP client
disconnecting mid-stream and a future voice channel's "stop speaking"
signal are both, structurally, just an `InterruptSignal` — the same
contract chat and voice share, so neither can drift from the other
(CONSTITUTION.md: Interface Independence).
"""

from __future__ import annotations

from typing import Protocol


class InterruptSignal(Protocol):
    async def is_interrupted(self) -> bool: ...
