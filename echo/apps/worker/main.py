"""Phase 1 scaffolding only: proves the worker container boots and can
consume a job off the Redis queue end-to-end. This is not the typed Job
Envelope contract (job type, version, input schema, idempotency key, retry
policy, timeout, provenance requirements, output schema, failure
classification) — that lands in Phase 3 (Docs/ARCHITECTURE.md, core/).
"""

import asyncio
import logging
import os

from redis.asyncio import Redis

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("echo.worker")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TEST_QUEUE_KEY = "echo:jobs:test"


async def run() -> None:
    client = Redis.from_url(REDIS_URL)
    logger.info("worker started, listening on %s", TEST_QUEUE_KEY)
    try:
        while True:
            item = await client.blpop([TEST_QUEUE_KEY], timeout=5)
            if item is None:
                continue
            _, payload = item
            logger.info("received test job: %s", payload.decode("utf-8"))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
