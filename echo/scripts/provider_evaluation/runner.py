"""Runs the actual live tests (PROMPT.md Phase 15: "Evaluate external
research providers through live tests rather than marketing claims") and
turns each raw HTTP response into `metrics.ProviderTestResult`s.

Every criterion below is either:
(a) derived from a real request made *right now* (`Outcome.PASS/FAIL/PARTIAL`),
(b) `Outcome.NOT_EVALUATED` because no credential was configured, or
(c) `Outcome.NOT_LIVE_TESTABLE` because the criterion isn't answerable from
    a single scripted request (reliability needs sustained monitoring over
    time; licensing/cost/documentation-quality are a documentation read, not
    an HTTP response; schema stability needs comparison across time) — noted
    honestly rather than assigned a fabricated score.

Two real tickers are used throughout: AAPL (large-cap, should be covered by
everything) and IBIT (a real Phase 12 holding, ETF — a plausibly weaker spot
for fundamentals-oriented providers), so "symbol coverage" reflects an
actually-relevant case, not an arbitrary pick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.config.settings import Settings
from scripts.provider_evaluation import clients
from scripts.provider_evaluation.clients import RawResponse
from scripts.provider_evaluation.metrics import Criterion, Need, Outcome, ProviderTestResult

_SYMBOL_PRIMARY = "AAPL"
_SYMBOL_SECONDARY = "IBIT"

_LATENCY_PASS_MS = 2000
_LATENCY_PARTIAL_MS = 5000


def latency_outcome(elapsed_ms: float) -> Outcome:
    if elapsed_ms <= _LATENCY_PASS_MS:
        return Outcome.PASS
    if elapsed_ms <= _LATENCY_PARTIAL_MS:
        return Outcome.PARTIAL
    return Outcome.FAIL


def auth_and_access_outcomes(response: RawResponse) -> tuple[Outcome, Outcome, str]:
    """Returns (authentication_success, actual_free_access, evidence)."""
    if response.error is not None:
        return Outcome.FAIL, Outcome.FAIL, f"request error: {response.error}"
    if response.status_code in (401, 403):
        return (
            Outcome.FAIL,
            Outcome.FAIL,
            f"HTTP {response.status_code}: {response.text_excerpt[:200]}",
        )
    if response.status_code == 402:
        return (
            Outcome.PASS,
            Outcome.FAIL,
            f"HTTP 402 Payment Required: {response.text_excerpt[:200]}",
        )
    if response.status_code == 429:
        return (
            Outcome.PASS,
            Outcome.PARTIAL,
            f"HTTP 429 rate limited on first request: {response.text_excerpt[:200]}",
        )
    if response.status_code != 200:
        return (
            Outcome.FAIL,
            Outcome.FAIL,
            f"HTTP {response.status_code}: {response.text_excerpt[:200]}",
        )
    body = response.json_body
    if body is None:
        return Outcome.PASS, Outcome.FAIL, "HTTP 200 but response body was not valid JSON"
    # Some free tiers return HTTP 200 with an error/upgrade message in the
    # body rather than a 4xx status — checked explicitly, not assumed absent.
    body_text = str(body).lower()
    if any(
        phrase in body_text
        for phrase in ("upgrade your plan", "premium", "not authorized", "api key is invalid")
    ):
        return (
            Outcome.PASS,
            Outcome.FAIL,
            f"HTTP 200 but body indicates a paywall/auth issue: {response.text_excerpt[:200]}",
        )
    if not body:
        return Outcome.PASS, Outcome.PARTIAL, "HTTP 200 with an empty body/list"
    return Outcome.PASS, Outcome.PASS, "HTTP 200 with a real, populated body"


def field_completeness(body: object, expected_fields: list[str]) -> tuple[Outcome, str]:
    if not isinstance(body, dict):
        if isinstance(body, list) and body and isinstance(body[0], dict):
            body = body[0]
        else:
            return Outcome.FAIL, "response body is not an object (or a list of objects)"
    present = [f for f in expected_fields if body.get(f) not in (None, "", [])]
    missing = [f for f in expected_fields if f not in present]
    if len(present) == len(expected_fields):
        return (
            Outcome.PASS,
            f"all {len(expected_fields)} expected fields present: {expected_fields}",
        )
    if present:
        return (
            Outcome.PARTIAL,
            f"{len(present)}/{len(expected_fields)} expected fields present; missing: {missing}",
        )
    return Outcome.FAIL, f"none of the expected fields present; missing: {missing}"


def response_has_real_data(response: RawResponse) -> bool:
    """Truthiness of `json_body` alone is not enough — a provider's error
    response (e.g. `{"Error Message": "..."}`) is a non-empty dict too. Real
    data requires both a populated body *and* `auth_and_access_outcomes`
    agreeing access actually succeeded, not just that some bytes came back."""
    _, access_outcome, _ = auth_and_access_outcomes(response)
    return bool(response.json_body) and access_outcome == Outcome.PASS


def rate_limit_evidence(response: RawResponse) -> tuple[Outcome, str]:
    rate_headers = {k: v for k, v in response.headers.items() if "ratelimit" in k.lower()}
    if rate_headers:
        return Outcome.PASS, f"rate-limit headers observed: {rate_headers}"
    return (
        Outcome.PARTIAL,
        "no rate-limit headers present on this response — not observed this pass",
    )


def _common_criteria(
    provider: str,
    need: Need,
    response: RawResponse,
    expected_fields: list[str],
    now: datetime,
) -> list[ProviderTestResult]:
    auth_outcome, access_outcome, access_evidence = auth_and_access_outcomes(response)
    results = [
        ProviderTestResult(
            provider, need, Criterion.AUTHENTICATION_SUCCESS, auth_outcome, access_evidence, now
        ),
        ProviderTestResult(
            provider, need, Criterion.ACTUAL_FREE_ACCESS, access_outcome, access_evidence, now
        ),
        ProviderTestResult(
            provider,
            need,
            Criterion.RESPONSE_LATENCY,
            latency_outcome(response.elapsed_ms),
            f"{response.elapsed_ms:.0f}ms",
            now,
        ),
    ]
    if response.json_body is not None:
        field_outcome, field_evidence = field_completeness(response.json_body, expected_fields)
        results.append(
            ProviderTestResult(
                provider, need, Criterion.FIELD_COMPLETENESS, field_outcome, field_evidence, now
            )
        )
        rate_outcome, rate_evidence = rate_limit_evidence(response)
        results.append(
            ProviderTestResult(
                provider, need, Criterion.RATE_LIMITS_OBSERVED, rate_outcome, rate_evidence, now
            )
        )
    return results


def _qualitative_provider_results(
    provider: str, now: datetime, *, documentation_quality: str, licensing: str, cost: str
) -> list[ProviderTestResult]:
    """Criteria PROMPT.md lists but that a single live script run cannot
    honestly answer — recorded once per provider, `need=None`, with the
    source of the note made explicit."""
    return [
        ProviderTestResult(
            provider,
            None,
            Criterion.DOCUMENTATION_QUALITY,
            Outcome.NOT_LIVE_TESTABLE,
            documentation_quality,
            now,
            notes="assessed from publicly published provider documentation, not live API evidence",
        ),
        ProviderTestResult(
            provider,
            None,
            Criterion.RELIABILITY,
            Outcome.NOT_LIVE_TESTABLE,
            "a single script run cannot establish uptime/reliability",
            now,
            notes="requires sustained monitoring over time, out of scope for a one-time run",
        ),
        ProviderTestResult(
            provider,
            None,
            Criterion.LICENSING_CONSTRAINTS,
            Outcome.NOT_LIVE_TESTABLE,
            licensing,
            now,
            notes="read from the provider's published terms of service, not live API evidence",
        ),
        ProviderTestResult(
            provider,
            None,
            Criterion.SCHEMA_STABILITY,
            Outcome.NOT_LIVE_TESTABLE,
            "a single observation cannot establish schema stability over time",
            now,
            notes="requires comparing responses across multiple dates/versions",
        ),
        ProviderTestResult(
            provider,
            None,
            Criterion.COST_AFTER_FREE_LIMITS,
            Outcome.NOT_LIVE_TESTABLE,
            cost,
            now,
            notes="read from the provider's published pricing page, not live API evidence",
        ),
    ]


async def evaluate_finnhub(settings: Settings, now: datetime) -> list[ProviderTestResult]:
    provider = "finnhub"
    if not settings.finnhub_api_key:
        return [
            ProviderTestResult(
                provider,
                need,
                Criterion.AUTHENTICATION_SUCCESS,
                Outcome.NOT_EVALUATED,
                "FINNHUB_API_KEY not configured",
                now,
            )
            for need in (
                Need.FUNDAMENTALS,
                Need.EARNINGS,
                Need.ANALYST_RATINGS,
                Need.COMPANY_NEWS,
                Need.MARKET_HISTORY,
            )
        ]
    key = settings.finnhub_api_key
    results: list[ProviderTestResult] = []

    url, params = clients.finnhub_url("/stock/profile2", key, symbol=_SYMBOL_PRIMARY)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider,
        Need.FUNDAMENTALS,
        response,
        ["name", "ticker", "marketCapitalization", "finnhubIndustry"],
        now,
    )
    second_url, second_params = clients.finnhub_url(
        "/stock/profile2", key, symbol=_SYMBOL_SECONDARY
    )
    second = await clients.fetch(second_url, params=second_params)
    primary_has_data = response_has_real_data(response)
    secondary_has_data = response_has_real_data(second)
    coverage_outcome = (
        Outcome.PASS
        if primary_has_data and secondary_has_data
        else Outcome.PARTIAL
        if primary_has_data or secondary_has_data
        else Outcome.FAIL
    )
    results.append(
        ProviderTestResult(
            provider,
            Need.FUNDAMENTALS,
            Criterion.SYMBOL_COVERAGE,
            coverage_outcome,
            f"{_SYMBOL_PRIMARY}: {'data' if primary_has_data else 'empty'}, "
            f"{_SYMBOL_SECONDARY}: {'data' if secondary_has_data else 'empty'}",
            now,
        )
    )

    url, params = clients.finnhub_url("/stock/earnings", key, symbol=_SYMBOL_PRIMARY)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.EARNINGS, response, ["actual", "estimate", "period", "symbol"], now
    )
    if isinstance(response.json_body, list) and response.json_body:
        periods = [
            str(r.get("period"))
            for r in response.json_body
            if isinstance(r, dict) and r.get("period")
        ]
        results.append(
            ProviderTestResult(
                provider,
                Need.EARNINGS,
                Criterion.HISTORICAL_DEPTH,
                Outcome.PASS,
                f"{len(periods)} periods returned, range {min(periods)} to {max(periods)}"
                if periods
                else "no dated periods in response",
                now,
            )
        )

    url, params = clients.finnhub_url("/stock/recommendation", key, symbol=_SYMBOL_PRIMARY)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.ANALYST_RATINGS, response, ["buy", "hold", "sell", "period"], now
    )

    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    url, params = clients.finnhub_url(
        "/company-news", key, symbol=_SYMBOL_PRIMARY, **{"from": week_ago, "to": today}
    )
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.COMPANY_NEWS, response, ["headline", "datetime", "source", "url"], now
    )
    if isinstance(response.json_body, list) and response.json_body:
        newest = max(
            item.get("datetime", 0) for item in response.json_body if isinstance(item, dict)
        )
        age = now - datetime.fromtimestamp(newest, tz=UTC) if newest else None
        results.append(
            ProviderTestResult(
                provider,
                Need.COMPANY_NEWS,
                Criterion.DATA_FRESHNESS,
                Outcome.PASS if age is not None and age < timedelta(days=2) else Outcome.PARTIAL,
                f"newest article is {age} old"
                if age is not None
                else "no timestamped articles returned",
                now,
            )
        )

    end_epoch = int(now.timestamp())
    start_epoch = int((now - timedelta(days=30)).timestamp())
    url, params = clients.finnhub_url(
        "/stock/candle",
        key,
        symbol=_SYMBOL_PRIMARY,
        resolution="D",
        **{"from": start_epoch, "to": end_epoch},
    )
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.MARKET_HISTORY, response, ["c", "h", "l", "o", "t"], now
    )

    results += _qualitative_provider_results(
        provider,
        now,
        documentation_quality="finnhub.io/docs/api — organized per-endpoint reference with example "
        "responses; free-tier limits stated per-endpoint rather than in one place",
        licensing="free tier: personal/non-commercial use per finnhub.io/pricing as published; "
        "commercial use requires a paid plan",
        cost="paid tiers start in the tens of USD/month per finnhub.io/pricing as published at "
        "evaluation time — verify current pricing before committing, it is not contractually fixed",
    )
    return results


async def evaluate_fmp(settings: Settings, now: datetime) -> list[ProviderTestResult]:
    provider = "fmp"
    if not settings.fmp_api_key:
        return [
            ProviderTestResult(
                provider,
                need,
                Criterion.AUTHENTICATION_SUCCESS,
                Outcome.NOT_EVALUATED,
                "FMP_API_KEY not configured",
                now,
            )
            for need in (
                Need.FUNDAMENTALS,
                Need.EARNINGS,
                Need.ANALYST_RATINGS,
                Need.COMPANY_NEWS,
                Need.SEC_FILINGS,
                Need.FORM_4_TRANSACTIONS,
                Need.MARKET_HISTORY,
            )
        ]
    key = settings.fmp_api_key
    results: list[ProviderTestResult] = []

    url, params = clients.fmp_v3_url(f"/profile/{_SYMBOL_PRIMARY}", key)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.FUNDAMENTALS, response, ["companyName", "mktCap", "sector", "industry"], now
    )
    second_url, second_params = clients.fmp_v3_url(f"/profile/{_SYMBOL_SECONDARY}", key)
    second = await clients.fetch(second_url, params=second_params)
    first_has_data = response_has_real_data(response)
    second_has_data = response_has_real_data(second)
    coverage_outcome = (
        Outcome.PASS
        if first_has_data and second_has_data
        else Outcome.PARTIAL
        if first_has_data or second_has_data
        else Outcome.FAIL
    )
    results.append(
        ProviderTestResult(
            provider,
            Need.FUNDAMENTALS,
            Criterion.SYMBOL_COVERAGE,
            coverage_outcome,
            f"{_SYMBOL_PRIMARY}: {'data' if first_has_data else 'empty'}, "
            f"{_SYMBOL_SECONDARY}: {'data' if second_has_data else 'empty'}",
            now,
        )
    )

    url, params = clients.fmp_v3_url(f"/earnings-surprises/{_SYMBOL_PRIMARY}", key)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.EARNINGS, response, ["date", "actualEarningResult", "estimatedEarning"], now
    )
    if isinstance(response.json_body, list) and response.json_body:
        dates = [
            str(r.get("date")) for r in response.json_body if isinstance(r, dict) and r.get("date")
        ]
        results.append(
            ProviderTestResult(
                provider,
                Need.EARNINGS,
                Criterion.HISTORICAL_DEPTH,
                Outcome.PASS,
                f"{len(dates)} reports, range {min(dates)} to {max(dates)}"
                if dates
                else "no dated reports",
                now,
            )
        )

    url, params = clients.fmp_v3_url(f"/analyst-stock-recommendations/{_SYMBOL_PRIMARY}", key)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider,
        Need.ANALYST_RATINGS,
        response,
        ["analystRatingsBuy", "analystRatingsHold", "analystRatingsSell"],
        now,
    )

    url, params = clients.fmp_v3_url("/stock_news", key, tickers=_SYMBOL_PRIMARY, limit=10)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.COMPANY_NEWS, response, ["title", "publishedDate", "site", "url"], now
    )
    if isinstance(response.json_body, list) and response.json_body:
        dated = [
            str(r.get("publishedDate"))
            for r in response.json_body
            if isinstance(r, dict) and r.get("publishedDate")
        ]
        results.append(
            ProviderTestResult(
                provider,
                Need.COMPANY_NEWS,
                Criterion.DATA_FRESHNESS,
                Outcome.PASS if dated else Outcome.PARTIAL,
                f"newest article dated {max(dated)}" if dated else "no dated articles returned",
                now,
            )
        )

    url, params = clients.fmp_v3_url(f"/sec_filings/{_SYMBOL_PRIMARY}", key)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.SEC_FILINGS, response, ["type", "fillingDate", "link"], now
    )

    url, params = clients.fmp_v4_url("/insider-trading", key, symbol=_SYMBOL_PRIMARY)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider,
        Need.FORM_4_TRANSACTIONS,
        response,
        ["transactionType", "transactionDate", "reportingName"],
        now,
    )

    url, params = clients.fmp_v3_url(f"/historical-price-full/{_SYMBOL_PRIMARY}", key)
    response = await clients.fetch(url, params=params)
    results += _common_criteria(
        provider, Need.MARKET_HISTORY, response, ["symbol", "historical"], now
    )
    if isinstance(response.json_body, dict) and isinstance(
        response.json_body.get("historical"), list
    ):
        history = response.json_body["historical"]
        dates = [str(r.get("date")) for r in history if isinstance(r, dict) and r.get("date")]
        results.append(
            ProviderTestResult(
                provider,
                Need.MARKET_HISTORY,
                Criterion.HISTORICAL_DEPTH,
                Outcome.PASS,
                f"{len(dates)} daily bars, range {min(dates)} to {max(dates)}"
                if dates
                else "no dated bars",
                now,
            )
        )

    results += _qualitative_provider_results(
        provider,
        now,
        documentation_quality="site.financialmodelingprep.com/developer/docs — extensive endpoint "
        "catalog, but versioning across v3/v4/stable is inconsistent and some documented endpoints "
        "are deprecated without clear migration notes",
        licensing="free tier explicitly for evaluation/personal use per FMP's published terms; "
        "redistribution and commercial use require a paid plan",
        cost="paid tiers start in the tens of USD/month per site.financialmodelingprep.com/pricing "
        "as published at evaluation time — verify current pricing before committing",
    )
    return results


async def evaluate_sec_edgar(settings: Settings, now: datetime) -> list[ProviderTestResult]:
    """Keyless and public — always evaluated regardless of configured API
    keys. Requires a real contact email in the User-Agent (SEC's fair-access
    policy); if none is configured, the request is still attempted, but a
    generic User-Agent is documented to risk throttling/rejection."""
    provider = "sec_edgar"
    contact = settings.research_contact_email or "no-contact-configured@example.invalid"
    headers = clients.sec_edgar_headers(contact)
    results: list[ProviderTestResult] = []

    ticker_map_response = await clients.fetch(clients.SEC_EDGAR_TICKER_MAP_URL, headers=headers)
    cik: str | None = None
    if isinstance(ticker_map_response.json_body, dict):
        for entry in ticker_map_response.json_body.values():
            if isinstance(entry, dict) and entry.get("ticker") == _SYMBOL_PRIMARY:
                cik = str(entry["cik_str"]).zfill(10)
                break

    if cik is None:
        for need in (Need.SEC_FILINGS, Need.FORM_4_TRANSACTIONS):
            results.append(
                ProviderTestResult(
                    provider,
                    need,
                    Criterion.AUTHENTICATION_SUCCESS,
                    Outcome.FAIL,
                    f"could not resolve a CIK for {_SYMBOL_PRIMARY} from the ticker map "
                    f"(HTTP {ticker_map_response.status_code})",
                    now,
                )
            )
        return results + _qualitative_provider_results(
            provider,
            now,
            documentation_quality=(
                "sec.gov/edgar/sec-api-documentation — precise, government-published, but "
                "requires manually mapping ticker to CIK first (no ticker-based lookup endpoint)"
            ),
            licensing=(
                "public domain / no license required (US government work) per SEC's published terms"
            ),
            cost="free, no paid tier exists",
        )

    url = clients.SEC_EDGAR_SUBMISSIONS_URL.format(cik=cik)
    response = await clients.fetch(url, headers=headers)
    results += _common_criteria(
        provider, Need.SEC_FILINGS, response, ["cik", "name", "filings"], now
    )
    if isinstance(response.json_body, dict):
        recent = response.json_body.get("filings", {}).get("recent", {})
        forms = recent.get("form", []) if isinstance(recent, dict) else []
        dates = recent.get("filingDate", []) if isinstance(recent, dict) else []
        form4_count = sum(1 for f in forms if f == "4")
        results.append(
            ProviderTestResult(
                provider,
                Need.FORM_4_TRANSACTIONS,
                Criterion.AUTHENTICATION_SUCCESS if form4_count else Criterion.FIELD_COMPLETENESS,
                Outcome.PASS if form4_count else Outcome.PARTIAL,
                f"{form4_count} Form 4 filings present in the {len(forms)} most recent filings for "
                f"{_SYMBOL_PRIMARY}"
                if forms
                else "no filings array returned",
                now,
            )
        )
        if dates:
            results.append(
                ProviderTestResult(
                    provider,
                    Need.SEC_FILINGS,
                    Criterion.HISTORICAL_DEPTH,
                    Outcome.PASS,
                    f"{len(dates)} filings, range {min(dates)} to {max(dates)}",
                    now,
                )
            )

    results += _qualitative_provider_results(
        provider,
        now,
        documentation_quality=(
            "sec.gov/edgar/sec-api-documentation — precise, government-published, but requires "
            "manually mapping ticker to CIK first (no ticker-based lookup endpoint)"
        ),
        licensing=(
            "public domain / no license required (US government work) per SEC's published terms"
        ),
        cost="free, no paid tier exists",
    )
    return results


async def evaluate_congressional_disclosures(now: datetime) -> list[ProviderTestResult]:
    """Keyless, public S3-hosted JSON dumps — no application code depends on
    the exact URL surviving (PROMPT.md Phase 15's own point: verify live,
    don't assume a documented endpoint still works)."""
    provider = "senate_house_stock_watcher"
    need = Need.CONGRESSIONAL_DISCLOSURES
    results: list[ProviderTestResult] = []

    senate = await clients.fetch(clients.SENATE_STOCK_WATCHER_URL)
    results += _common_criteria(
        provider, need, senate, ["transaction_date", "senator", "ticker", "type"], now
    )
    house = await clients.fetch(clients.HOUSE_STOCK_WATCHER_URL)
    results += _common_criteria(
        provider, need, house, ["transaction_date", "representative", "ticker", "type"], now
    )

    results += _qualitative_provider_results(
        provider,
        now,
        documentation_quality=(
            "no formal API documentation — these are unversioned static JSON dumps hosted on "
            "public S3 buckets, discovered via the projects' GitHub READMEs, not an API contract"
        ),
        licensing=(
            "no explicit license found published alongside the data at evaluation time — treat "
            "as unverified provenance until a license is confirmed, do not assume redistribution "
            "rights"
        ),
        cost=(
            "free — no paid tier exists; also no SLA, so no cost guarantee of continued "
            "availability"
        ),
    )
    return results


async def evaluate_reddit(now: datetime) -> list[ProviderTestResult]:
    """Attempted despite low expectations, per PROMPT.md Phase 15's own
    instruction not to trust an assumption without an actual request."""
    provider = "reddit_public_json"
    need = Need.COMPANY_NEWS
    response = await clients.fetch(
        clients.REDDIT_SEARCH_URL,
        params={"q": _SYMBOL_PRIMARY, "restrict_sr": "1", "sort": "new", "limit": 10},
        headers=clients.reddit_headers(),
    )
    results = _common_criteria(provider, need, response, ["data"], now)
    results += _qualitative_provider_results(
        provider,
        now,
        documentation_quality="the unauthenticated .json endpoints used here are undocumented/"
        "unofficial; Reddit's real, documented API requires OAuth app registration",
        licensing="Reddit's API terms require registration and prohibit unauthenticated scripted "
        "access at any real volume — this test itself is likely out of bounds for sustained use",
        cost="Reddit's official API introduced paid pricing in 2023 for high-volume commercial use",
    )
    return results


async def run_all(settings: Settings) -> list[ProviderTestResult]:
    now = datetime.now(UTC)
    results: list[ProviderTestResult] = []
    results += await evaluate_finnhub(settings, now)
    results += await evaluate_fmp(settings, now)
    results += await evaluate_sec_edgar(settings, now)
    results += await evaluate_congressional_disclosures(now)
    results += await evaluate_reddit(now)
    return results
