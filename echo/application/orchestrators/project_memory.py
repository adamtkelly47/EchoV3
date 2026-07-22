"""Coordinates Projects + Memory (PROMPT.md Phase 23 implement item 9:
"memory integration"). No direct "Projects -> Memory" row exists in
Docs/DOMAIN_OWNERSHIP.md's Cross-Domain Interaction Matrix, but the
matrix's own general rule applies: "Domains SHALL interact only through:
Application orchestration, Published domain events, Public interfaces" —
and the one directly analogous row that *is* listed
("Conversation -> Memory: Application Command") uses exactly this
mechanism, so this orchestrator follows the same pattern rather than
inventing a new one.

Only project Decisions are linked into Memory, not Status Updates —
a decision is the durable, "worth remembering later" kind of fact this
domain produces (Docs/DOMAIN_OWNERSHIP.md: "historical decisions" is named
directly in CONSTITUTION.md's Product Mission); a routine status update is
not. A narrower, real scope rather than linking every append-only record
into Memory speculatively.

The created memory is always a `CANDIDATE` (domains/memory/service.py's own
`record_candidate` — "extraction only ever produces CANDIDATE records"),
never auto-confirmed — a project decision is a real fact about what was
decided, but whether it's worth being a durable, always-recalled memory is
still the user's call, the same discipline every other memory-producing
pathway in this codebase already follows.
"""

from __future__ import annotations

from domains.memory.schemas import MemoryRecord
from domains.memory.service import MemoryService
from domains.projects.schemas import Decision
from domains.projects.service import ProjectService

_DECISION_MEMORY_CONFIDENCE = 0.9


class ProjectMemoryOrchestrator:
    def __init__(self, projects: ProjectService, memory: MemoryService) -> None:
        self._projects = projects
        self._memory = memory

    async def record_decision_with_memory(
        self,
        project_id: str,
        description: str,
        rationale: str | None = None,
        source_context: str | None = None,
    ) -> tuple[Decision, MemoryRecord]:
        project = await self._projects.get_project(project_id)
        decision = await self._projects.record_decision(
            project_id, description, rationale, source_context
        )
        content = f'Decided for project "{project.name}": {description}'
        if rationale:
            content += f" (rationale: {rationale})"
        memory = await self._memory.record_candidate(
            user_id=project.user_id,
            subject_key=f"project_decision:{project_id}",
            content=content,
            confidence=_DECISION_MEMORY_CONFIDENCE,
            source_type="project_decision",
            source_id=decision.decision_id,
            correlation_id=source_context,
        )
        return decision, memory
