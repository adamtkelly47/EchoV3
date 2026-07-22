"""SEC EDGAR adapter — plain httpx against SEC's public REST API, no
third-party SDK. Keyless, but SEC's fair-access policy requires a
descriptive User-Agent with a real, reachable contact address — live-
verified working in Phase 15 (Docs/DECISION_LOG.md's Phase 15 entry: 6/7
criteria passed, real Form 4 and filing-history data confirmed for AAPL).

No ticker-based lookup endpoint exists — a ticker must be resolved to a CIK
via the separate `company_tickers.json` map first, then the submissions
endpoint queried by that CIK. Both steps live inside `get_issuer_profile` so
domains/research/service.py's `ResearchProviderPort` Protocol stays a single
method, matching every other provider adapter in this codebase.

Phase 18 added Form 4 (insider transaction) retrieval. The submissions
endpoint above only lists *that* a Form 4 was filed (form type, accession
number, filing date) — the actual transaction content requires a second
fetch of that filing's own XML document, at a path only discoverable via
the accession's own `index.json` (the `primaryDocument` filename in
`submissions.json` points at an XSLT-rendered HTML view, not the raw XML).
The real XML schema below (`_parse_form4_xml`) was verified against several
live UnitedHealth Group Form 4 filings before being written — including the
one uncertain field, the Rule 10b5-1 trading-plan indicator: it is a
document-level (not per-transaction) `<aff10b5One>0|1</aff10b5One>` element,
confirmed by inspecting real filings rather than assumed from memory.
`derivativeTable` (options/derivatives) is deliberately not parsed — a
documented scope limitation (Docs/DECISION_LOG.md's Phase 18 entry), not a
silent gap. A filing with more than one `reportingOwner` (joint filers) is
also a known, documented simplification: only the first is used.
"""

from __future__ import annotations

# SEC EDGAR's own filing XML — a trusted source, not user-submitted input.
import xml.etree.ElementTree as ET  # nosec B405
from typing import Any

import httpx

from core.errors import ProviderUnavailableError

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_nopad}/{accession_nodash}/index.json"
)
_FILING_DOCUMENT_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_nopad}/{accession_nodash}/{filename}"
)


class SecEdgarAdapter:
    def __init__(self, contact_email: str) -> None:
        self._headers = {
            "User-Agent": f"Echo Personal AI Operating System (research domain) {contact_email}"
        }

    async def get_issuer_profile(self, ticker: str) -> dict[str, Any]:
        cik = await self._resolve_cik(ticker)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_SUBMISSIONS_URL.format(cik=cik), headers=self._headers)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"SEC EDGAR submissions request failed: {exc}") from exc

    async def get_form4_filings(self, cik: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Lists the `limit` most recent Form 4 filings for `cik` — just
        enough to discover each one's accession number, not the transaction
        content itself (that's `get_form4_document`)."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_SUBMISSIONS_URL.format(cik=cik), headers=self._headers)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"SEC EDGAR submissions request failed: {exc}") from exc

        recent = body.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        filings = [
            {"accession_number": accessions[i], "filing_date": dates[i]}
            for i, form in enumerate(forms)
            if form == "4"
        ]
        return filings[:limit]

    async def get_form4_document(self, cik: str, accession_number: str) -> dict[str, Any]:
        """Resolves the filing's own raw XML filename (via `index.json` —
        never the `primaryDocument` from `submissions.json`, which is an
        XSLT-rendered HTML view, not the machine-readable XML) and parses
        it into a raw dict. Provider speaks in primitives (a plain dict),
        same as every other provider in this codebase — translation into
        typed domain objects happens in domains/research/policies.py."""
        cik_nopad = str(int(cik))
        accession_nodash = accession_number.replace("-", "")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                index_response = await client.get(
                    _FILING_INDEX_URL.format(
                        cik_nopad=cik_nopad, accession_nodash=accession_nodash
                    ),
                    headers=self._headers,
                )
                index_response.raise_for_status()
                items = index_response.json().get("directory", {}).get("item", [])
                xml_name = next(
                    (
                        item["name"]
                        for item in items
                        if item.get("name", "").endswith(".xml") and "index" not in item["name"]
                    ),
                    None,
                )
                if xml_name is None:
                    raise ProviderUnavailableError(
                        f"SEC EDGAR: no XML document found for accession {accession_number!r}"
                    )
                doc_response = await client.get(
                    _FILING_DOCUMENT_URL.format(
                        cik_nopad=cik_nopad, accession_nodash=accession_nodash, filename=xml_name
                    ),
                    headers=self._headers,
                )
                doc_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"SEC EDGAR Form 4 document request failed: {exc}"
            ) from exc
        return _parse_form4_xml(doc_response.text)

    async def _resolve_cik(self, ticker: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(_TICKER_MAP_URL, headers=self._headers)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"SEC EDGAR ticker map request failed: {exc}") from exc
        for entry in body.values():
            if isinstance(entry, dict) and entry.get("ticker") == ticker:
                return str(entry["cik_str"]).zfill(10)
        raise ProviderUnavailableError(f"SEC EDGAR: no CIK found for ticker {ticker!r}")


def _text(elem: ET.Element | None) -> str | None:
    if elem is None or elem.text is None:
        return None
    stripped = elem.text.strip()
    return stripped or None


def _child_text(parent: ET.Element | None, path: str) -> str | None:
    if parent is None:
        return None
    return _text(parent.find(path))


def _parse_form4_xml(xml_text: str) -> dict[str, Any]:
    # SEC's own trusted, government-published XML — not user-supplied input.
    root = ET.fromstring(xml_text)  # nosec B314
    issuer = root.find("issuer")
    owner = root.find("reportingOwner")
    owner_id = owner.find("reportingOwnerId") if owner is not None else None
    relationship = owner.find("reportingOwnerRelationship") if owner is not None else None

    footnotes = {
        footnote.get("id"): (footnote.text or "").strip()
        for footnote in root.findall(".//footnotes/footnote")
        if footnote.get("id")
    }

    transactions = []
    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        footnote_ids = [ref.get("id") for ref in txn.findall(".//footnoteId") if ref.get("id")]
        transactions.append(
            {
                "transaction_date": _child_text(txn.find("transactionDate"), "value"),
                "transaction_code": _child_text(txn.find("transactionCoding"), "transactionCode"),
                "shares": _child_text(txn.find("transactionAmounts/transactionShares"), "value"),
                "price_per_share": _child_text(
                    txn.find("transactionAmounts/transactionPricePerShare"), "value"
                ),
                "acquired_disposed": _child_text(
                    txn.find("transactionAmounts/transactionAcquiredDisposedCode"), "value"
                ),
                "shares_owned_following": _child_text(
                    txn.find("postTransactionAmounts/sharesOwnedFollowingTransaction"), "value"
                ),
                "footnote_ids": footnote_ids,
            }
        )

    return {
        "issuer_cik": _child_text(issuer, "issuerCik"),
        "issuer_name": _child_text(issuer, "issuerName"),
        "reporting_owner_cik": _child_text(owner_id, "rptOwnerCik"),
        "reporting_owner_name": _child_text(owner_id, "rptOwnerName"),
        "is_director": _child_text(relationship, "isDirector") == "1",
        "is_officer": _child_text(relationship, "isOfficer") == "1",
        "is_ten_percent_owner": _child_text(relationship, "isTenPercentOwner") == "1",
        "officer_title": _child_text(relationship, "officerTitle"),
        "aff10b5_one": _text(root.find("aff10b5One")) == "1",
        "transactions": transactions,
        "footnotes": footnotes,
    }
