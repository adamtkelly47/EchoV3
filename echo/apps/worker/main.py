"""Worker entrypoint. PROMPT.md Phase 24 implement item 2: "trigger
schedules" — consumes the real `monitoring.evaluate` `JobEnvelope` the
scheduler now enqueues, replacing the Phase 1 throwaway `echo:jobs:test`
string payload entirely (this module's own prior docstring named this
exact phase as the trigger for that upgrade). A failed job is logged and
dropped, never silently retried in a way that could duplicate an alert —
`domains.system.service.SystemService.raise_alert`'s own dedup-by-key
check is what actually protects against duplicate alerts either way
(PROMPT.md Phase 24 verification 2), so a safe-by-construction retry here
would be redundant, not load-bearing.
"""

from __future__ import annotations

import asyncio

from redis.asyncio import Redis

from application.calendar_provider_factory import build_google_calendar_provider
from application.orchestrators.monitoring import MonitoringEvaluateInput, MonitoringOrchestrator
from application.portfolio_provider_factory import build_schwab_provider
from application.research_provider_factory import (
    build_form4_providers,
    build_legislator_reference_provider,
    build_news_providers,
    build_ptr_providers,
    build_research_providers,
)
from core.config import get_settings
from core.jobs import JobEnvelope
from core.logging import configure_logging, get_logger
from core.observability import correlation_scope
from core.time import SystemClock
from domains.calendar.repository import (
    PostgresCalendarCredentialRepository,
    PostgresCalendarEventRepository,
)
from domains.calendar.service import CalendarService
from domains.portfolio.repository import (
    PostgresComplianceResultRepository,
    PostgresHypotheticalTradeRepository,
    PostgresIPSRepository,
    PostgresPortfolioRepository,
    PostgresSchwabCredentialRepository,
)
from domains.portfolio.service import PortfolioService
from domains.research.repository import PostgresResearchRepository
from domains.research.service import ResearchService
from domains.system.repository import PostgresSystemRepository
from domains.system.service import SystemService
from infrastructure.database.engine import session_scope
from infrastructure.database.repositories.audit import PostgresAuditRepository
from infrastructure.database.repositories.provenance import (
    PostgresComputedValueRecordRepository,
    PostgresSourceRecordRepository,
)
from infrastructure.secrets.encryption import SecretCipher

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("echo.worker")

MONITORING_QUEUE_KEY = "echo:jobs:monitoring"


async def _run_monitoring_evaluate() -> None:
    async with session_scope() as session:
        cipher = SecretCipher(settings.secret_encryption_key or "")
        state_secret = settings.secret_encryption_key or ""
        clock = SystemClock()
        audit = PostgresAuditRepository(session)

        system = SystemService(PostgresSystemRepository(session), audit, clock)
        portfolio = PortfolioService(
            PostgresSchwabCredentialRepository(session),
            PostgresPortfolioRepository(session),
            PostgresSourceRecordRepository(session),
            build_schwab_provider(settings),
            cipher,
            audit,
            clock,
            state_secret,
            PostgresComputedValueRecordRepository(session),
            PostgresIPSRepository(session),
            PostgresComplianceResultRepository(session),
            PostgresHypotheticalTradeRepository(session),
        )
        calendar = CalendarService(
            PostgresCalendarCredentialRepository(session),
            PostgresCalendarEventRepository(session),
            build_google_calendar_provider(settings),
            cipher,
            audit,
            clock,
            state_secret,
        )
        research = ResearchService(
            PostgresResearchRepository(session),
            PostgresSourceRecordRepository(session),
            build_research_providers(settings),
            audit,
            clock,
            build_news_providers(settings),
            build_form4_providers(settings),
            build_ptr_providers(settings),
            build_legislator_reference_provider(settings),
        )
        orchestrator = MonitoringOrchestrator(system, portfolio, calendar, research, audit, clock)
        runs = await orchestrator.evaluate_all_enabled_monitors()
        logger.info("monitoring.evaluate: %d monitor(s) evaluated", len(runs))


async def _handle_job(payload: bytes) -> None:
    try:
        envelope = JobEnvelope[MonitoringEvaluateInput].model_validate_json(payload)
    except Exception:  # noqa: BLE001 — a malformed job must not crash the worker loop
        logger.warning("dropping malformed job payload: %s", payload[:200])
        return

    with correlation_scope(envelope.correlation_id):
        if envelope.job_type != "monitoring.evaluate":
            logger.warning("unrecognized job_type %r, dropping", envelope.job_type)
            return
        try:
            await _run_monitoring_evaluate()
        except Exception:  # noqa: BLE001 — one failed sweep must not kill the worker process
            logger.exception("monitoring.evaluate job %s failed", envelope.job_id)


async def run() -> None:
    client = Redis.from_url(settings.redis_url)
    logger.info("worker started, listening on %s", MONITORING_QUEUE_KEY)
    try:
        while True:
            item = await client.blpop([MONITORING_QUEUE_KEY], timeout=5)
            if item is None:
                continue
            _, payload = item
            await _handle_job(payload)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
