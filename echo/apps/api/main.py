"""Phase 1 scaffolding only: proves the backend container boots and can reach
its dependencies (Neon, Redis, Ollama). No domain, capability, or request
pipeline logic belongs here — that begins in Phase 3+ (see Docs/REQUEST_LIFECYCLE.md).
Config/logging are read directly from the environment for now; centralized
core/config and core/logging are Phase 3 deliverables (Docs/ARCHITECTURE.md).
"""

import logging
import os
from typing import TypedDict

import asyncpg
import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("echo.api")

app = FastAPI(title="Echo API", version="0.1.0")

DATABASE_URL = os.environ.get("DATABASE_URL")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")


class DependencyStatus(TypedDict, total=False):
    ok: bool
    detail: str


class DependenciesResponse(TypedDict):
    status: str
    dependencies: dict[str, DependencyStatus]


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness only — used by Docker's own HEALTHCHECK. Always fast, no dependency calls."""
    return {"status": "ok"}


@app.get("/health/dependencies")
async def health_dependencies() -> DependenciesResponse:
    """Readiness against real dependencies. Used for Phase 1 manual verification."""
    results: dict[str, DependencyStatus] = {
        "database": await _check_database(),
        "redis": await _check_redis(),
        "ollama": await _check_ollama(),
    }

    overall_ok = all(dep["ok"] for dep in results.values())
    return {"status": "ok" if overall_ok else "degraded", "dependencies": results}


async def _check_database() -> DependencyStatus:
    if not DATABASE_URL:
        return {"ok": False, "detail": "DATABASE_URL is not set"}
    try:
        conn = await asyncpg.connect(DATABASE_URL, timeout=5)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 — surfaced as a health status, not raised
        logger.warning("database health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}


async def _check_redis() -> DependencyStatus:
    client = Redis.from_url(REDIS_URL, socket_timeout=5)
    try:
        await client.ping()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}
    finally:
        await client.close()


async def _check_ollama() -> DependencyStatus:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("ollama health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}
