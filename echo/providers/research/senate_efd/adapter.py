"""Senate Electronic Financial Disclosure (eFD) system adapter — plain
httpx against efdsearch.senate.gov, no third-party SDK. Unlike SEC EDGAR
(Phase 15/16/18), this site has no public REST API: it is a Django app whose
search results are only reachable after a session accepts a "prohibition
agreement" (a real, required click-through — verified live before writing
this adapter), after which its internal DataTables AJAX endpoint
(`/search/report/data/`) returns real JSON, and each Periodic Transaction
Report (PTR) is a real server-rendered HTML page at `/search/view/ptr/{id}/`
containing a genuine transactions table — for electronically-filed reports
only. Some senators still file PTRs on paper (`/search/view/paper/{id}/`,
scanned images) — a documented scope limitation, not a silent gap: paper
filings are surfaced in `list_ptr_filings` with `report_kind="paper"` so
callers can skip them explicitly, the same "identified, not silently
dropped" discipline as Phase 18's joint-filer simplification.

The DataTable's `report_types` checkbox value for "Periodic Transactions"
(`11`) and the transaction table's real column layout (`#`, Transaction
Date, Owner, Ticker, Asset Name, Asset Type, Type, Amount, Comment) were
both confirmed live against the real site before this adapter was written,
per this project's live-verification-before-parsing discipline (Docs/
DECISION_LOG.md's Phase 18 entry set the precedent; the Phase 19 entry
records this site's own findings).

Real transaction "Amount" values are always a disclosed *range* (e.g.
"$1,001 - $15,000") or an open-ended "Over $X" — the Ethics in Government
Act (which the STOCK Act extends to cover securities transactions) has
never required exact dollar disclosure. This adapter returns that string
completely unparsed; `domains/research/policies.py`'s `parse_ptr_amount_range`
is where the low/high boundary floats are derived, deliberately never
collapsed into one fabricated point figure (PROMPT.md Phase 19 verification
1: "transaction ranges are not converted into false exact amounts").
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from core.errors import ProviderUnavailableError

_HOME_URL = "https://efdsearch.senate.gov/search/home/"
_SEARCH_URL = "https://efdsearch.senate.gov/search/"
_REPORT_DATA_URL = "https://efdsearch.senate.gov/search/report/data/"
_REPORT_VIEW_URL = "https://efdsearch.senate.gov/search/view/{kind}/{report_id}/"

# "Periodic Transactions" — the report_type checkbox value on the real
# search form (confirmed live; the site also defines 7=Annual, 10=Extension,
# 14=Blind Trust, 15=Other, none of which carry transaction data).
_PTR_REPORT_TYPE = 11

_CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
_REPORT_LINK_RE = re.compile(r"/search/view/(ptr|paper)/([0-9a-f-]+)/")


class SenateEfdAdapter:
    def __init__(self, contact_email: str) -> None:
        self._headers = {
            "User-Agent": f"Echo Personal AI Operating System (research domain) {contact_email}"
        }

    async def list_ptr_filings(self, *, start_date: str, limit: int = 50) -> list[dict[str, Any]]:
        """Lists Periodic Transaction Report filings submitted on or after
        `start_date` (`YYYY-MM-DD`), most recent first — just enough to
        discover each report's id and kind, not its transaction content
        (that's `get_ptr_transactions`)."""
        try:
            submitted_start = datetime.strptime(start_date, "%Y-%m-%d").strftime(
                "%m/%d/%Y 00:00:00"
            )
        except ValueError as exc:
            raise ProviderUnavailableError(f"invalid start_date {start_date!r}: {exc}") from exc

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30, headers=self._headers
            ) as client:
                csrftoken = await self._accept_agreement(client)
                response = await client.post(
                    _REPORT_DATA_URL,
                    data={
                        "draw": 1,
                        "columns[0][data]": 0,
                        "start": 0,
                        "length": limit,
                        "report_types": f"[{_PTR_REPORT_TYPE}]",
                        "filer_types": "[]",
                        "submitted_start_date": submitted_start,
                        "submitted_end_date": "",
                        "candidate_state": "",
                        "senator_state": "",
                        "office_id": "",
                        "first_name": "",
                        "last_name": "",
                        "csrfmiddlewaretoken": csrftoken,
                    },
                    headers={"Referer": _SEARCH_URL, "X-CSRFToken": csrftoken},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Senate eFD report search failed: {exc}") from exc

        filings = []
        for row in payload.get("data", []):
            if len(row) < 5:
                continue
            first_name, last_name, office, link_html, filed_at = row[:5]
            match = _REPORT_LINK_RE.search(link_html)
            if match is None:
                continue
            filings.append(
                {
                    "report_kind": match.group(1),  # "ptr" (electronic) or "paper" (scanned)
                    "report_id": match.group(2),
                    "first_name": first_name,
                    "last_name": last_name,
                    "office": office,
                    "filed_at": filed_at,
                }
            )
        return filings

    async def get_ptr_transactions(self, report_id: str) -> dict[str, Any]:
        """Fetches and parses one electronically-filed PTR's real
        transactions table. Only valid for `report_kind="ptr"` filings from
        `list_ptr_filings` — paper filings have no structured table to
        parse (this method will raise `ProviderUnavailableError` for one,
        since `/search/view/paper/{id}/` renders a scanned document viewer
        instead)."""
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30, headers=self._headers
            ) as client:
                await self._accept_agreement(client)
                response = await client.get(
                    _REPORT_VIEW_URL.format(kind="ptr", report_id=report_id)
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Senate eFD report fetch failed: {exc}") from exc
        return _parse_ptr_html(response.text)

    async def _accept_agreement(self, client: httpx.AsyncClient) -> str:
        """Every real search or report-view request 403s without first
        accepting the site's own click-through prohibition agreement in the
        same session — verified live; there is no way to skip this step.
        Returns the session's CSRF token, needed by both the caller (for
        the DataTable POST) and future requests in this same client."""
        try:
            home = await client.get(_HOME_URL)
            home.raise_for_status()
            match = _CSRF_RE.search(home.text)
            if match is None:
                raise ProviderUnavailableError("Senate eFD home page had no CSRF token")
            token = match.group(1)
            await client.post(
                _HOME_URL,
                data={"csrfmiddlewaretoken": token, "prohibition_agreement": "1"},
                headers={"Referer": _HOME_URL},
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Senate eFD agreement step failed: {exc}") from exc
        csrftoken = client.cookies.get("csrftoken")
        if not csrftoken:
            raise ProviderUnavailableError("Senate eFD did not issue a session csrftoken cookie")
        return csrftoken


def _cell_text(cell: Any) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


def _parse_ptr_html(html: str) -> dict[str, Any]:
    """Real column layout confirmed live: `#`, Transaction Date, Owner,
    Ticker, Asset Name, Asset Type, Type, Amount, Comment. Ticker is a
    hyperlink to an external quote page (or absent for non-equity assets);
    `Asset Name` sometimes carries an extra sub-line of option details
    (e.g. "Option Type: Call ... Strike price: ... Expires: ...") folded
    into the same cell's text — kept as part of the raw asset name string
    rather than parsed out, since PROMPT.md Phase 19's scope is the
    non-derivative transaction fields, matching Phase 18's own decision not
    to parse Form 4's `derivativeTable`."""
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find("h1")
    filer = soup.find("h2", class_="filedReport")
    rows = []
    table = soup.find("table", class_="table")
    if isinstance(table, Tag):
        body = table.find("tbody")
        if isinstance(body, Tag):
            for tr in body.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 9:
                    continue
                ticker_link = cells[3].find("a")
                rows.append(
                    {
                        "transaction_date": _cell_text(cells[1]),
                        "owner": _cell_text(cells[2]),
                        "ticker": _cell_text(ticker_link) if ticker_link else None,
                        "asset_name": _cell_text(cells[4]),
                        "asset_type": _cell_text(cells[5]),
                        "transaction_type": _cell_text(cells[6]),
                        "amount_text": _cell_text(cells[7]),
                        "comment": _cell_text(cells[8]),
                    }
                )
    return {
        "report_title": _cell_text(header) if header is not None else None,
        "filer_text": _cell_text(filer) if filer is not None else None,
        "transactions": rows,
    }
