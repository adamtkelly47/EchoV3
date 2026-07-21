"""Phase 1 scaffolding only: proves the scheduler container boots and can
enqueue work for the worker via Redis. This is not the real schedule
definition system (cadences, quiet hours, duplicate-execution prevention) —
that is a Phase 24 (Proactive monitoring foundation) concern built on top of
the Phase 3 job envelope. The scheduler never performs domain work itself,
per Docs/DOMAIN_OWNERSHIP.md and CONSTITUTION.md.
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime

from redis.asyncio import Redis

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("echo.scheduler")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TEST_QUEUE_KEY = "echo:jobs:test"
INTERVAL_SECONDS = 30


async def run() -> None:
    client = Redis.from_url(REDIS_URL)
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
