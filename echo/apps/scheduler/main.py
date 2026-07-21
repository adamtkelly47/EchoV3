"""Scheduler entrypoint. Still enqueues the Phase 1 throwaway test job — see
apps/worker/main.py for why that isn't upgraded to the real JobEnvelope
contract yet. This is not the real schedule definition system (cadences,
quiet hours, duplicate-execution prevention) — that is a Phase 24
(Proactive monitoring foundation) concern. The scheduler never performs
domain work itself, per Docs/DOMAIN_OWNERSHIP.md and CONSTITUTION.md.
"""

import asyncio
import json
from datetime import UTC, datetime

from redis.asyncio import Redis

from core.config import get_settings
from core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("echo.scheduler")

TEST_QUEUE_KEY = "echo:jobs:test"
INTERVAL_SECONDS = 30


async def run() -> None:
    client = Redis.from_url(settings.redis_url)
    logger.info("scheduler started, enqueuing a test job every %ss", INTERVAL_SECONDS)
    try:
        while True:
            payload = json.dumps(
                {"type": "system.ping", "created_at": datetime.now(UTC).isoformat()}
            )
            await client.rpush(TEST_QUEUE_KEY, payload)
            logger.info("enqueued test job")
            await asyncio.sleep(INTERVAL_SECONDS)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
