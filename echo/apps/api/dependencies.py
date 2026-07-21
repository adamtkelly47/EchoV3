"""FastAPI dependency wiring — construction happens at the application
boundary (CONSTITUTION.md: Dependency Injection), never inside domain code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.calendar_provider_factory import build_google_calendar_provider
from application.capabilities.calendar_read import (
    build_calendar_free_busy_capability,
    build_calendar_list_events_capability,
)
from application.capabilities.current_time import build_current_time_capability
from application.model_gateway_factory import ModelGatewayPort, build_model_gateway
from application.orchestrators.calendar_writes import CalendarWriteOrchestrator
from application.orchestrators.conversation import ConversationOrchestrator
from application.orchestrators.memory_extraction import MemoryExtractionOrchestrator
from application.portfolio_provider_factory import build_schwab_provider
from core.config import get_settings
from core.time import SystemClock
from domains.approvals.repository import (
    PostgresApprovalDecisionRepository,
    PostgresApprovalProposalRepository,
)
from domains.approvals.service import ApprovalService
from domains.calendar.repository import (
    PostgresCalendarCredentialRepository,
    PostgresCalendarEventRepository,
)
from domains.calendar.service import CalendarProviderPort, CalendarService
from domains.capabilities.service import CapabilityExecutor, CapabilityRegistry
from domains.conversation.repository import PostgresConversationRepository
from domains.conversation.service import ConversationService
from domains.memory.repository import PostgresMemoryRepository
from domains.memory.service import MemoryService
from domains.portfolio.repository import (
    PostgresPortfolioRepository,
    PostgresSchwabCredentialRepository,
)
from domains.portfolio.service import PortfolioProviderPort, PortfolioService
from infrastructure.database.engine import session_scope
from infrastructure.database.repositories.audit import PostgresAuditRepository
from infrastructure.database.repositories.observability import PostgresToolCallRepository
from infrastructure.database.repositories.provenance import PostgresSourceRecordRepository
from infrastructure.secrets.encryption import SecretCipher


@lru_cache
def get_google_calendar_provider() -> CalendarProviderPort:
    return build_google_calendar_provider(get_settings())


@lru_cache
def get_schwab_provider() -> PortfolioProviderPort:
    return build_schwab_provider(get_settings())


@lru_cache
def get_secret_cipher() -> SecretCipher:
    return SecretCipher(get_settings().secret_encryption_key or "")


def get_oauth_state_secret() -> str:
    return get_settings().secret_encryption_key or ""


@lru_cache
def get_capability_registry() -> CapabilityRegistry:
    """Process-wide: capabilities are registered once at first use, not
    per-request (CONSTITUTION.md: Capability Discovery — registration, not
    a per-call decision)."""
    registry = CapabilityRegistry()
    registry.register(build_current_time_capability(SystemClock()))
    provider = get_google_calendar_provider()
    cipher = get_secret_cipher()
    state_secret = get_oauth_state_secret()
    registry.register(build_calendar_list_events_capability(provider, cipher, state_secret))
    registry.register(build_calendar_free_busy_capability(provider, cipher, state_secret))
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


def get_memory_service(
    session: AsyncSession = Depends(get_db_session),
) -> MemoryService:
    return MemoryService(
        PostgresMemoryRepository(session), PostgresAuditRepository(session), SystemClock()
    )


def get_memory_extraction_orchestrator(
    memory: MemoryService = Depends(get_memory_service),
    gateway: ModelGatewayPort = Depends(get_model_gateway),
) -> MemoryExtractionOrchestrator:
    return MemoryExtractionOrchestrator(memory, gateway)


def get_calendar_service(
    session: AsyncSession = Depends(get_db_session),
) -> CalendarService:
    return CalendarService(
        PostgresCalendarCredentialRepository(session),
        PostgresCalendarEventRepository(session),
        get_google_calendar_provider(),
        get_secret_cipher(),
        PostgresAuditRepository(session),
        SystemClock(),
        get_oauth_state_secret(),
    )


def get_approval_service(
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalService:
    return ApprovalService(
        PostgresApprovalProposalRepository(session),
        PostgresApprovalDecisionRepository(session),
        PostgresAuditRepository(session),
        SystemClock(),
    )


def get_calendar_write_orchestrator(
    approvals: ApprovalService = Depends(get_approval_service),
    calendar: CalendarService = Depends(get_calendar_service),
) -> CalendarWriteOrchestrator:
    return CalendarWriteOrchestrator(approvals, calendar, get_google_calendar_provider())


def get_portfolio_service(
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioService:
    return PortfolioService(
        PostgresSchwabCredentialRepository(session),
        PostgresPortfolioRepository(session),
        PostgresSourceRecordRepository(session),
        get_schwab_provider(),
        get_secret_cipher(),
        PostgresAuditRepository(session),
        SystemClock(),
        get_oauth_state_secret(),
    )
