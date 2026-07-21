#!/usr/bin/env python
"""PROMPT.md Phase 15 entry point: run every configured provider's live
tests and write the dated decision report.

Usage: python scripts/run_provider_evaluation.py

Requires the app's normal environment (core.config.settings reads
FINNHUB_API_KEY / FMP_API_KEY / RESEARCH_CONTACT_EMAIL from .env) — run this
the same way any other backend script in this repo is run (inside the
backend container, where those are already loaded).

Writes to `scripts/provider_evaluation/output/` (gitignored), not directly to
Docs/decisions/ — the backend container only mounts `echo/`, not the repo
root, so Docs/ isn't reachable from inside it. Copy the result out with:
`docker compose cp backend:/app/scripts/provider_evaluation/output/<file> Docs/decisions/<file>`
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import get_settings  # noqa: E402
from scripts.provider_evaluation.report import render_report  # noqa: E402
from scripts.provider_evaluation.runner import run_all  # noqa: E402

_OUTPUT_DIR = Path(__file__).resolve().parent / "provider_evaluation" / "output"


async def main() -> None:
    settings = get_settings()
    results = await run_all(settings)
    generated_at = datetime.now(UTC)
    report = render_report(results, generated_at)

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _OUTPUT_DIR / f"PROVIDER_EVALUATION_{generated_at.date().isoformat()}.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path} ({len(results)} test results)")


if __name__ == "__main__":
    asyncio.run(main())
