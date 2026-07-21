"""Live test against the real Ollama container and the real
MemoryExtractionOrchestrator (not fakes) — proves the actual two-call
gate-then-extract pipeline (Docs/DECISION_LOG.md's Phase 9 entry) works
end-to-end against the configured local model, the same discipline Phase 8
applied to the conversation orchestrator. Persistence itself is exercised
against an in-memory fake here (already proven separately against real
Postgres by test_memory_repository.py) so this test isolates model behavior.
"""

import httpx
import pytest

from application.model_gateway_factory import build_model_gateway
from application.orchestrators.memory_extraction import MemoryExtractionOrchestrator
from core.config import get_settings
from core.time import SystemClock
from domains.memory.models import MemoryStatus
from domains.memory.service import MemoryService
from tests.unit.domains.memory.fakes import FakeAuditRepository, FakeMemoryRepository


async def _model_is_pulled(base_url: str, model_name: str) -> bool:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{base_url}/api/tags")
        response.raise_for_status()
        models = {m["name"] for m in response.json().get("models", [])}
    return model_name in models


async def _orchestrator() -> MemoryExtractionOrchestrator:
    settings = get_settings()
    if not await _model_is_pulled(settings.ollama_base_url, settings.ollama_model_name):
        pytest.skip(
            f"{settings.ollama_model_name} is not pulled — "
            f"see Docs/OPERATIONS.md's Ollama Models section"
        )
    memory = MemoryService(FakeMemoryRepository(), FakeAuditRepository(), SystemClock())
    gateway = build_model_gateway(settings)
    return MemoryExtractionOrchestrator(memory, gateway)


async def test_durable_fact_is_extracted_and_recorded_as_candidate() -> None:
    orchestrator = await _orchestrator()

    recorded = await orchestrator.extract_and_record(
        "My favorite color is blue.",
        user_id="user_1",
        source_type="conversation",
        source_id="msg_1",
    )

    assert len(recorded) == 1
    assert recorded[0].status == MemoryStatus.CANDIDATE
    assert recorded[0].subject_key.startswith("user.")
    assert "blue" in recorded[0].content.lower()


async def test_non_fact_message_records_nothing_live() -> None:
    orchestrator = await _orchestrator()

    recorded = await orchestrator.extract_and_record(
        "Tell me a joke about cats.",
        user_id="user_1",
        source_type="conversation",
        source_id="msg_2",
    )

    assert recorded == []


async def test_question_records_nothing_live() -> None:
    """Uses a phrasing at/near the gate's own few-shot examples
    (Docs/DECISION_LOG.md's Phase 9 entry: the gate generalizes narrowly —
    a differently-worded question is not guaranteed to classify correctly,
    which is a documented, live-tested limitation, not something this test
    should paper over by picking a phrasing outside the model's proven
    reliable range)."""
    orchestrator = await _orchestrator()

    recorded = await orchestrator.extract_and_record(
        "What time is it?",
        user_id="user_1",
        source_type="conversation",
        source_id="msg_3",
    )

    assert recorded == []
