"""Backend entrypoint. Domain, capability, and request-pipeline logic does
not live here yet — that begins Phase 5+ (see Docs/REQUEST_LIFECYCLE.md).
This module wires the Phase 3 core contracts (config, logging, correlation)
into a running FastAPI app and exposes the Phase 1 health endpoints.
"""

from collections.abc import Awaitable, Callable
from typing import TypedDict

import asyncpg
import httpx
from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis

from core.config import get_settings
from core.logging import configure_logging, get_logger
from core.observability import correlation_scope

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("echo.api")

app = FastAPI(title="Echo API", version="0.1.0")


@app.middleware("http")
async def add_correlation_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Every request gets a correlation id (CONSTITUTION.md: Correlation
    IDs), taken from an inbound header when present so callers can trace a
    request across service boundaries, otherwise generated fresh."""
    incoming = request.headers.get("x-correlation-id")
    with correlation_scope(incoming) as correlation_id:
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response


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
    if not settings.database_url:
        return {"ok": False, "detail": "DATABASE_URL is not set"}
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=5)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 — surfaced as a health status, not raised
        logger.warning("database health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}


async def _check_redis() -> DependencyStatus:
    client = Redis.from_url(settings.redis_url, socket_timeout=5)
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
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("ollama health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}
