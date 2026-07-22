"""Backend entrypoint. Wires the core contracts (config, logging,
correlation) and the API routes into a running FastAPI app.
"""

from collections.abc import Awaitable, Callable
from typing import TypedDict

import asyncpg
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from apps.api.routes.approvals import router as approvals_router
from apps.api.routes.calendar import router as calendar_router
from apps.api.routes.conversations import router as conversations_router
from apps.api.routes.dashboard import router as dashboard_router
from apps.api.routes.email import router as email_router
from apps.api.routes.memory import router as memory_router
from apps.api.routes.portfolio import router as portfolio_router
from apps.api.routes.projects import router as projects_router
from apps.api.routes.research import router as research_router
from apps.api.routes.system import router as system_router
from apps.api.routes.trust import router as trust_router
from core.config import get_settings
from core.errors import EchoError
from core.logging import configure_logging, get_logger
from core.observability import correlation_scope, get_correlation_id

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("echo.api")

app = FastAPI(title="Echo API", version="0.1.0")
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(calendar_router)
app.include_router(email_router)
app.include_router(approvals_router)
app.include_router(portfolio_router)
app.include_router(research_router)
app.include_router(dashboard_router)
app.include_router(projects_router)
app.include_router(system_router)
app.include_router(trust_router)

# Frontend runs on a different origin (localhost:3000 vs. this API's
# localhost:8000) — the browser needs explicit CORS permission. Origin is
# hardcoded to the local dev frontend for this phase; real deployment
# configuration is a later phase's concern, not retrofitted here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    # PATCH added alongside GET/POST: several routes (calendar/email event
    # modification, project status, monitor enable/disable) always used
    # PATCH, but no frontend page called one from the browser until the
    # Phase 23-27 pages did — a real, previously-latent gap, not a new
    # capability.
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.exception_handler(EchoError)
async def handle_echo_error(request: Request, exc: EchoError) -> JSONResponse:
    """Every EchoError subclass declares its own `http_status`/`code`
    (core/errors/base.py) — this is the one place that gets translated into
    a wire response, so no route handler needs its own try/except
    (PROMPT.md Phase 10 verification: "read failures are surfaced
    honestly" — surfaced live testing found every route up to this point
    returning a bare, bodyless 500 for a domain error; this closes that gap
    for every route, not just Calendar's)."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error_code": exc.code,
            "message": exc.message,
            "correlation_id": exc.correlation_id or get_correlation_id(),
        },
    )


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
