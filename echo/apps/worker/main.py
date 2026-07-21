"""Worker entrypoint. Still consumes the throwaway `echo:jobs:test` string
payload from Phase 1 — that gets replaced by the real `core.jobs.JobEnvelope`
contract (proven independently via unit tests this phase) once a real job
type is introduced (Phase 24+). This module now wires the Phase 3 core
contracts (config, logging, correlation) in place of the Phase 1 ad hoc
`os.environ`/`logging.basicConfig` calls.
"""

import asyncio

from redis.asyncio import Redis

from core.config import get_settings
from core.logging import configure_logging, get_logger
from core.observability import correlation_scope

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("echo.worker")

TEST_QUEUE_KEY = "echo:jobs:test"


async def run() -> None:
    client = Redis.from_url(settings.redis_url)
    logger.info("worker started, listening on %s", TEST_QUEUE_KEY)
    try:
        while True:
            item = await client.blpop([TEST_QUEUE_KEY], timeout=5)
            if item is None:
                continue
            _, payload = item
            with correlation_scope():
                logger.info("received test job: %s", payload.decode("utf-8"))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
