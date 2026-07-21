# Shared image for api, worker, and scheduler — one codebase, three runtime
# entrypoints, per Docs/decisions/ADR_0001. docker-compose.yml selects the
# entrypoint per service via `command:`.

FROM python:3.12-slim

# curl is needed for the api service's Docker healthcheck (compose.yml).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY core ./core
COPY apps ./apps
COPY infrastructure ./infrastructure
COPY migrations ./migrations

# Base image's bundled pip has known advisories (pip-audit) — upgrade first.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
