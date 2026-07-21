"""FastAPI dependency wiring — construction happens at the application
boundary (CONSTITUTION.md: Dependency Injection), never inside domain code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.capabilities.current_time import build_current_time_capability
from application.model_gateway_factory import ModelGatewayPort, build_model_gateway
from application.orchestrators.conversation import ConversationOrchestrator
from core.config import get_settings
from core.time import SystemClock
from domains.capabilities.service import CapabilityExecutor, CapabilityRegistry
from domains.conversation.repository import PostgresConversationRepository
from domains.conversation.service import ConversationService
from infrastructure.database.engine import session_scope
from infrastructure.database.repositories.observability import PostgresToolCallRepository


@lru_cache
def get_capability_registry() -> CapabilityRegistry:
    """Process-wide: capabilities are registered once at first use, not
    per-request (CONSTITUTION.md: Capability Discovery — registration, not
    a per-call decision)."""
    registry = CapabilityRegistry()
    registry.register(build_current_time_capability(SystemClock()))
    return registry


@lru_cache
def get_model_gateway() -> ModelGatewayPort:
    return build_model_gateway(get_settings())


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


def get_conversation_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationService:
    return ConversationService(PostgresConversationRepository(session), SystemClock())


def get_capability_executor(
    session: AsyncSession = Depends(get_db_session),
) -> CapabilityExecutor:
    return CapabilityExecutor(
        get_capability_registry(), PostgresToolCallRepository(session), SystemClock()
    )


def get_conversation_orchestrator(
    conversations: ConversationService = Depends(get_conversation_service),
    executor: CapabilityExecutor = Depends(get_capability_executor),
    gateway: ModelGatewayPort = Depends(get_model_gateway),
) -> ConversationOrchestrator:
    return ConversationOrchestrator(conversations, executor, gateway)
