"""Scheduler entrypoint. PROMPT.md Phase 24 implement item 2: "trigger
schedules" — enqueues a real `monitoring.evaluate` `JobEnvelope` on a fixed
interval, replacing the Phase 1 throwaway test job entirely now that a
real job type exists (this file's own prior docstring named this exact
phase as the trigger for that upgrade). The scheduler still never performs
domain work itself, per Docs/DOMAIN_OWNERSHIP.md and CONSTITUTION.md — it
only enqueues; `apps/worker/main.py` does the actual evaluation.
"""

import asyncio
from datetime import UTC, datetime

from redis.asyncio import Redis

from application.orchestrators.monitoring import MonitoringEvaluateInput
from core.config import get_settings
from core.jobs import JobEnvelope
from core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("echo.scheduler")

MONITORING_QUEUE_KEY = "echo:jobs:monitoring"
# 5 minutes: frequent enough to be genuinely "proactive" (PROMPT.md Phase
# 24's own objective) without re-hitting Schwab/Google Calendar/Research
# on every tick — the same order of magnitude as domains/calendar/service.
# py's own 5-minute cache TTL from Phase 10.
MONITORING_INTERVAL_SECONDS = 300


async def run() -> None:
    client = Redis.from_url(settings.redis_url)
    logger.info(
        "scheduler started, enqueuing monitoring.evaluate every %ss", MONITORING_INTERVAL_SECONDS
    )
    try:
        while True:
            now = datetime.now(UTC)
            job = JobEnvelope[MonitoringEvaluateInput](
                job_type="monitoring.evaluate",
                input=MonitoringEvaluateInput(),
                idempotency_key=f"monitoring-evaluate-{now.isoformat()}",
                timeout_seconds=120,
                created_at=now,
            )
            await client.rpush(MONITORING_QUEUE_KEY, job.model_dump_json())
            logger.info("enqueued monitoring.evaluate job %s", job.job_id)
            await asyncio.sleep(MONITORING_INTERVAL_SECONDS)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
