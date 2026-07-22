"""unitedstates/congress-legislators reference dataset adapter (Phase 19)
— a public, actively-maintained GitHub project publishing structured
member/committee data the government itself does not offer as a clean API
(congress.gov and efdsearch.senate.gov both do not). Keyless, YAML over
raw.githubusercontent.com; reachability and real file names (`legislators-
current.yaml`, `committees-current.yaml`, `committee-membership-current.
yaml` — not the `.json` variants this project used to also publish, which
404 as of this phase) were confirmed live before writing this adapter.

This is a *current-snapshot* dataset, not a historical time series:
`committee-membership-current.yaml` reflects committee assignments as of
whenever it was last updated upstream, with no per-date effective range.
Real committee assignments are made once per two-year Congress and are
generally stable within it, so `domains/research/policies.py` scopes any
use of this snapshot to the current Congress's own date range (derived from
each legislator's own `terms` entries, which *are* genuinely date-ranged) —
never claiming committee membership for a transaction predating the current
Congress (PROMPT.md Phase 19 verification 2: "committee membership uses the
membership effective at the relevant date").
"""

from __future__ import annotations

from typing import Any

import httpx
import yaml

from core.errors import ProviderUnavailableError

_LEGISLATORS_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "legislators-current.yaml"
)
_COMMITTEES_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "committees-current.yaml"
)
_COMMITTEE_MEMBERSHIP_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "committee-membership-current.yaml"
)


class CongressLegislatorsAdapter:
    async def get_legislators(self) -> list[dict[str, Any]]:
        return await self._get_yaml_list(_LEGISLATORS_URL)

    async def get_committees(self) -> list[dict[str, Any]]:
        return await self._get_yaml_list(_COMMITTEES_URL)

    async def get_committee_membership(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_COMMITTEE_MEMBERSHIP_URL)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"congress-legislators committee-membership fetch failed: {exc}"
            ) from exc
        parsed = yaml.safe_load(response.text)
        return parsed if isinstance(parsed, dict) else {}

    async def _get_yaml_list(self, url: str) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"congress-legislators fetch failed: {exc}") from exc
        parsed = yaml.safe_load(response.text)
        return parsed if isinstance(parsed, list) else []
