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
from application.orchestrators.insider_intelligence import InsiderIntelligenceOrchestrator
from application.orchestrators.memory_extraction import MemoryExtractionOrchestrator
from application.orchestrators.monitoring import MonitoringOrchestrator
from application.orchestrators.news_intelligence import NewsIntelligenceOrchestrator
from application.orchestrators.project_memory import ProjectMemoryOrchestrator
from application.orchestrators.trust import TrustOrchestrator
from application.portfolio_provider_factory import build_schwab_provider
from application.queries.dashboard_query import DashboardQueryService
from application.queries.trust_dashboard_query import TrustDashboardQueryService
from application.research_provider_factory import (
    build_form4_providers,
    build_legislator_reference_provider,
    build_news_providers,
    build_ptr_providers,
    build_research_providers,
)
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
    PostgresComplianceResultRepository,
    PostgresIPSRepository,
    PostgresPortfolioRepository,
    PostgresSchwabCredentialRepository,
)
from domains.portfolio.service import PortfolioProviderPort, PortfolioService
from domains.projects.repository import PostgresProjectRepository
from domains.projects.service import ProjectService
from domains.research.repository import PostgresResearchRepository
from domains.research.service import (
    Form4ProviderPort,
    LegislatorReferencePort,
    NewsProviderPort,
    PtrProviderPort,
    ResearchProviderPort,
    ResearchService,
)
from domains.system.repository import PostgresSystemRepository
from domains.system.service import SystemService
from infrastructure.database.engine import session_scope
from infrastructure.database.repositories.audit import PostgresAuditRepository
from infrastructure.database.repositories.observability import (
    PostgresModelCallRepository,
    PostgresToolCallRepository,
)
from infrastructure.database.repositories.provenance import (
    PostgresComputedValueRecordRepository,
    PostgresSourceRecordRepository,
)
from infrastructure.secrets.encryption import SecretCipher


@lru_cache
def get_google_calendar_provider() -> CalendarProviderPort:
    return build_google_calendar_provider(get_settings())


@lru_cache
def get_schwab_provider() -> PortfolioProviderPort:
    return build_schwab_provider(get_settings())


@lru_cache
def get_research_providers() -> dict[str, ResearchProviderPort]:
    return build_research_providers(get_settings())


@lru_cache
def get_news_providers() -> dict[str, NewsProviderPort]:
    return build_news_providers(get_settings())


@lru_cache
def get_form4_providers() -> dict[str, Form4ProviderPort]:
    return build_form4_providers(get_settings())


@lru_cache
def get_ptr_providers() -> dict[str, PtrProviderPort]:
    return build_ptr_providers(get_settings())


@lru_cache
def get_legislator_reference_provider() -> LegislatorReferencePort | None:
    return build_legislator_reference_provider(get_settings())


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
        PostgresComputedValueRecordRepository(session),
        PostgresIPSRepository(session),
        PostgresComplianceResultRepository(session),
    )


def get_research_service(
    session: AsyncSession = Depends(get_db_session),
) -> ResearchService:
    return ResearchService(
        PostgresResearchRepository(session),
        PostgresSourceRecordRepository(session),
        get_research_providers(),
        PostgresAuditRepository(session),
        SystemClock(),
        get_news_providers(),
        get_form4_providers(),
        get_ptr_providers(),
        get_legislator_reference_provider(),
    )


def get_news_intelligence_orchestrator(
    research: ResearchService = Depends(get_research_service),
    portfolio: PortfolioService = Depends(get_portfolio_service),
    gateway: ModelGatewayPort = Depends(get_model_gateway),
) -> NewsIntelligenceOrchestrator:
    return NewsIntelligenceOrchestrator(research, portfolio, gateway, SystemClock())


def get_insider_intelligence_orchestrator(
    research: ResearchService = Depends(get_research_service),
    gateway: ModelGatewayPort = Depends(get_model_gateway),
) -> InsiderIntelligenceOrchestrator:
    return InsiderIntelligenceOrchestrator(research, gateway)


def get_project_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProjectService:
    return ProjectService(
        PostgresProjectRepository(session), PostgresAuditRepository(session), SystemClock()
    )


def get_project_memory_orchestrator(
    projects: ProjectService = Depends(get_project_service),
    memory: MemoryService = Depends(get_memory_service),
) -> ProjectMemoryOrchestrator:
    return ProjectMemoryOrchestrator(projects, memory)


def get_dashboard_query_service(
    portfolio: PortfolioService = Depends(get_portfolio_service),
    calendar: CalendarService = Depends(get_calendar_service),
    approvals: ApprovalService = Depends(get_approval_service),
    conversations: ConversationService = Depends(get_conversation_service),
    projects: ProjectService = Depends(get_project_service),
) -> DashboardQueryService:
    return DashboardQueryService(
        portfolio, calendar, approvals, conversations, projects, SystemClock(), get_settings()
    )


def get_system_service(
    session: AsyncSession = Depends(get_db_session),
) -> SystemService:
    return SystemService(
        PostgresSystemRepository(session), PostgresAuditRepository(session), SystemClock()
    )


def get_monitoring_orchestrator(
    system: SystemService = Depends(get_system_service),
    portfolio: PortfolioService = Depends(get_portfolio_service),
    calendar: CalendarService = Depends(get_calendar_service),
    research: ResearchService = Depends(get_research_service),
    session: AsyncSession = Depends(get_db_session),
) -> MonitoringOrchestrator:
    return MonitoringOrchestrator(
        system, portfolio, calendar, research, PostgresAuditRepository(session), SystemClock()
    )


def get_trust_orchestrator(
    memory: MemoryService = Depends(get_memory_service),
    system: SystemService = Depends(get_system_service),
) -> TrustOrchestrator:
    return TrustOrchestrator(memory, system)


def get_trust_dashboard_query_service(
    portfolio: PortfolioService = Depends(get_portfolio_service),
    system: SystemService = Depends(get_system_service),
    session: AsyncSession = Depends(get_db_session),
) -> TrustDashboardQueryService:
    return TrustDashboardQueryService(
        portfolio,
        system,
        PostgresAuditRepository(session),
        PostgresModelCallRepository(session),
        PostgresToolCallRepository(session),
        SystemClock(),
    )
