# Provider Evaluation Report — 2026-07-21

Version: 1.0
Generated: 2026-07-21T20:35:35.014033+00:00
Owner: Echo Project

## Purpose

PROMPT.md Phase 15: live-tested evaluation of candidate external research data providers against 13 measured criteria across 8 research needs. Every PASS/FAIL/PARTIAL outcome below came from an actual request made at generation time, not a provider's own marketing claim. **No permanent provider is selected by this report** — that decision belongs to PROMPT.md Phase 16 and beyond.

Outcomes:

- `pass` / `fail` / `partial` — from an actual live request.
- `not_evaluated` — no credential was configured for this provider this pass.
- `not_live_testable` — the criterion isn't answerable from a single scripted request (documentation quality, licensing, cost, schema stability over time, reliability over time); noted with its source instead of a fabricated score.

## finnhub

**Needs served:** analyst_ratings, company_news, earnings, fundamentals, market_history
**Summary:** pass=23 fail=3 partial=2 not_evaluated=0 not_live_testable=5

### finnhub — analyst_ratings

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | pass | HTTP 200 with a real, populated body |
| actual_free_access | pass | HTTP 200 with a real, populated body |
| response_latency | pass | 233ms |
| field_completeness | pass | all 4 expected fields present: ['buy', 'hold', 'sell', 'period'] |
| rate_limits_observed | pass | rate-limit headers observed: {'x-ratelimit-limit': '60', 'x-ratelimit-remaining': '58', 'x-ratelimit-reset': '1784666230'} |

### finnhub — company_news

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | pass | HTTP 200 with a real, populated body |
| actual_free_access | pass | HTTP 200 with a real, populated body |
| response_latency | pass | 273ms |
| field_completeness | pass | all 4 expected fields present: ['headline', 'datetime', 'source', 'url'] |
| rate_limits_observed | pass | rate-limit headers observed: {'x-ratelimit-limit': '60', 'x-ratelimit-remaining': '57', 'x-ratelimit-reset': '1784666230'} |
| data_freshness | pass | newest article is 0:58:58.880764 old |

### finnhub — earnings

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | pass | HTTP 200 with a real, populated body |
| actual_free_access | pass | HTTP 200 with a real, populated body |
| response_latency | pass | 236ms |
| field_completeness | pass | all 4 expected fields present: ['actual', 'estimate', 'period', 'symbol'] |
| rate_limits_observed | pass | rate-limit headers observed: {'x-ratelimit-limit': '60', 'x-ratelimit-remaining': '59', 'x-ratelimit-reset': '1784666230'} |
| historical_depth | pass | 4 periods returned, range 2025-06-30 to 2026-03-31 |

### finnhub — fundamentals

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | pass | HTTP 200 with a real, populated body |
| actual_free_access | pass | HTTP 200 with a real, populated body |
| response_latency | pass | 261ms |
| field_completeness | pass | all 4 expected fields present: ['name', 'ticker', 'marketCapitalization', 'finnhubIndustry'] |
| rate_limits_observed | pass | rate-limit headers observed: {'x-ratelimit-limit': '60', 'x-ratelimit-remaining': '59', 'x-ratelimit-reset': '1784666191'} |
| symbol_coverage | partial | AAPL: data, IBIT: empty |

### finnhub — market_history

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {"error":"You don't have access to this resource."} |
| actual_free_access | fail | HTTP 403: {"error":"You don't have access to this resource."} |
| response_latency | pass | 233ms |
| field_completeness | fail | none of the expected fields present; missing: ['c', 'h', 'l', 'o', 't'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### finnhub — provider-level criteria

| Criterion | Outcome | Evidence | Notes |
|---|---|---|---|
| documentation_quality | not_live_testable | finnhub.io/docs/api — organized per-endpoint reference with example responses; free-tier limits stated per-endpoint rather than in one place | assessed from publicly published provider documentation, not live API evidence |
| reliability | not_live_testable | a single script run cannot establish uptime/reliability | requires sustained monitoring over time, out of scope for a one-time run |
| licensing_constraints | not_live_testable | free tier: personal/non-commercial use per finnhub.io/pricing as published; commercial use requires a paid plan | read from the provider's published terms of service, not live API evidence |
| schema_stability | not_live_testable | a single observation cannot establish schema stability over time | requires comparing responses across multiple dates/versions |
| cost_after_free_limits | not_live_testable | paid tiers start in the tens of USD/month per finnhub.io/pricing as published at evaluation time — verify current pricing before committing, it is not contractually fixed | read from the provider's published pricing page, not live API evidence |

## fmp

**Needs served:** analyst_ratings, company_news, earnings, form_4_transactions, fundamentals, market_history, sec_filings
**Summary:** pass=7 fail=22 partial=7 not_evaluated=0 not_live_testable=5

### fmp — analyst_ratings

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 188ms |
| field_completeness | fail | none of the expected fields present; missing: ['analystRatingsBuy', 'analystRatingsHold', 'analystRatingsSell'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### fmp — company_news

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 187ms |
| field_completeness | fail | none of the expected fields present; missing: ['title', 'publishedDate', 'site', 'url'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### fmp — earnings

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 195ms |
| field_completeness | fail | none of the expected fields present; missing: ['date', 'actualEarningResult', 'estimatedEarning'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### fmp — form_4_transactions

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 185ms |
| field_completeness | fail | none of the expected fields present; missing: ['transactionType', 'transactionDate', 'reportingName'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### fmp — fundamentals

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 203ms |
| field_completeness | fail | none of the expected fields present; missing: ['companyName', 'mktCap', 'sector', 'industry'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |
| symbol_coverage | fail | AAPL: empty, IBIT: empty |

### fmp — market_history

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 180ms |
| field_completeness | fail | none of the expected fields present; missing: ['symbol', 'historical'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### fmp — sec_filings

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| actual_free_access | fail | HTTP 403: {   "Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025. Please  |
| response_latency | pass | 173ms |
| field_completeness | fail | none of the expected fields present; missing: ['type', 'fillingDate', 'link'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |

### fmp — provider-level criteria

| Criterion | Outcome | Evidence | Notes |
|---|---|---|---|
| documentation_quality | not_live_testable | site.financialmodelingprep.com/developer/docs — extensive endpoint catalog, but versioning across v3/v4/stable is inconsistent and some documented endpoints are deprecated without clear migration notes | assessed from publicly published provider documentation, not live API evidence |
| reliability | not_live_testable | a single script run cannot establish uptime/reliability | requires sustained monitoring over time, out of scope for a one-time run |
| licensing_constraints | not_live_testable | free tier explicitly for evaluation/personal use per FMP's published terms; redistribution and commercial use require a paid plan | read from the provider's published terms of service, not live API evidence |
| schema_stability | not_live_testable | a single observation cannot establish schema stability over time | requires comparing responses across multiple dates/versions |
| cost_after_free_limits | not_live_testable | paid tiers start in the tens of USD/month per site.financialmodelingprep.com/pricing as published at evaluation time — verify current pricing before committing | read from the provider's published pricing page, not live API evidence |

## reddit_public_json

**Needs served:** company_news
**Summary:** pass=1 fail=2 partial=0 not_evaluated=0 not_live_testable=5

### reddit_public_json — company_news

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: <body class=theme-beta><div><style>.theme-light,:root{--rem360:22.5rem;--rem320:20rem;--rem192:12rem;--rem144:9rem;--rem128:8rem;--rem96:6rem;--rem90:5.625rem;--rem88:5.5rem;--rem64:4rem;--rem56:3.5re |
| actual_free_access | fail | HTTP 403: <body class=theme-beta><div><style>.theme-light,:root{--rem360:22.5rem;--rem320:20rem;--rem192:12rem;--rem144:9rem;--rem128:8rem;--rem96:6rem;--rem90:5.625rem;--rem88:5.5rem;--rem64:4rem;--rem56:3.5re |
| response_latency | pass | 140ms |

### reddit_public_json — provider-level criteria

| Criterion | Outcome | Evidence | Notes |
|---|---|---|---|
| documentation_quality | not_live_testable | the unauthenticated .json endpoints used here are undocumented/unofficial; Reddit's real, documented API requires OAuth app registration | assessed from publicly published provider documentation, not live API evidence |
| reliability | not_live_testable | a single script run cannot establish uptime/reliability | requires sustained monitoring over time, out of scope for a one-time run |
| licensing_constraints | not_live_testable | Reddit's API terms require registration and prohibit unauthenticated scripted access at any real volume — this test itself is likely out of bounds for sustained use | read from the provider's published terms of service, not live API evidence |
| schema_stability | not_live_testable | a single observation cannot establish schema stability over time | requires comparing responses across multiple dates/versions |
| cost_after_free_limits | not_live_testable | Reddit's official API introduced paid pricing in 2023 for high-volume commercial use | read from the provider's published pricing page, not live API evidence |

## sec_edgar

**Needs served:** form_4_transactions, sec_filings
**Summary:** pass=6 fail=0 partial=1 not_evaluated=0 not_live_testable=5

### sec_edgar — form_4_transactions

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | pass | 589 Form 4 filings present in the 1000 most recent filings for AAPL |

### sec_edgar — sec_filings

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | pass | HTTP 200 with a real, populated body |
| actual_free_access | pass | HTTP 200 with a real, populated body |
| response_latency | pass | 246ms |
| field_completeness | pass | all 3 expected fields present: ['cik', 'name', 'filings'] |
| rate_limits_observed | partial | no rate-limit headers present on this response — not observed this pass |
| historical_depth | pass | 1000 filings, range 2015-05-29 to 2026-06-17 |

### sec_edgar — provider-level criteria

| Criterion | Outcome | Evidence | Notes |
|---|---|---|---|
| documentation_quality | not_live_testable | sec.gov/edgar/sec-api-documentation — precise, government-published, but requires manually mapping ticker to CIK first (no ticker-based lookup endpoint) | assessed from publicly published provider documentation, not live API evidence |
| reliability | not_live_testable | a single script run cannot establish uptime/reliability | requires sustained monitoring over time, out of scope for a one-time run |
| licensing_constraints | not_live_testable | public domain / no license required (US government work) per SEC's published terms | read from the provider's published terms of service, not live API evidence |
| schema_stability | not_live_testable | a single observation cannot establish schema stability over time | requires comparing responses across multiple dates/versions |
| cost_after_free_limits | not_live_testable | free, no paid tier exists | read from the provider's published pricing page, not live API evidence |

## senate_house_stock_watcher

**Needs served:** congressional_disclosures
**Summary:** pass=2 fail=4 partial=0 not_evaluated=0 not_live_testable=5

### senate_house_stock_watcher — congressional_disclosures

| Criterion | Outcome | Evidence |
|---|---|---|
| authentication_success | fail | HTTP 403: <?xml version="1.0" encoding="UTF-8"?> <Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>1W988KH2NV1EYN54</RequestId><HostId>LmPTK2zkU7scQXovKOeWM9cu/ClcDT+f1Q+8H+bS9x3KESs+Fn |
| actual_free_access | fail | HTTP 403: <?xml version="1.0" encoding="UTF-8"?> <Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>1W988KH2NV1EYN54</RequestId><HostId>LmPTK2zkU7scQXovKOeWM9cu/ClcDT+f1Q+8H+bS9x3KESs+Fn |
| response_latency | pass | 242ms |
| authentication_success | fail | HTTP 403: <?xml version="1.0" encoding="UTF-8"?> <Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>1W91G5NDRCR8E74Z</RequestId><HostId>jHIZxQhtIlm7iSBKqBRWHjKIliFSnfDJjNQfhn0wnx0Z/lcRvY |
| actual_free_access | fail | HTTP 403: <?xml version="1.0" encoding="UTF-8"?> <Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>1W91G5NDRCR8E74Z</RequestId><HostId>jHIZxQhtIlm7iSBKqBRWHjKIliFSnfDJjNQfhn0wnx0Z/lcRvY |
| response_latency | pass | 210ms |

### senate_house_stock_watcher — provider-level criteria

| Criterion | Outcome | Evidence | Notes |
|---|---|---|---|
| documentation_quality | not_live_testable | no formal API documentation — these are unversioned static JSON dumps hosted on public S3 buckets, discovered via the projects' GitHub READMEs, not an API contract | assessed from publicly published provider documentation, not live API evidence |
| reliability | not_live_testable | a single script run cannot establish uptime/reliability | requires sustained monitoring over time, out of scope for a one-time run |
| licensing_constraints | not_live_testable | no explicit license found published alongside the data at evaluation time — treat as unverified provenance until a license is confirmed, do not assume redistribution rights | read from the provider's published terms of service, not live API evidence |
| schema_stability | not_live_testable | a single observation cannot establish schema stability over time | requires comparing responses across multiple dates/versions |
| cost_after_free_limits | not_live_testable | free — no paid tier exists; also no SLA, so no cost guarantee of continued availability | read from the provider's published pricing page, not live API evidence |

## Known candidates not evaluated this pass

No credentials were available to even attempt a request against these — they carry no `ProviderTestResult`s above, not a `not_evaluated` outcome.

- **Polygon.io** — market history, fundamentals — no account/API key available this pass
- **Bloomberg** — enterprise-tier pricing data — no account available this pass
- **Reuters** — news — no account/API key available this pass
- **an alternate congressional-disclosure source** — senate_house_stock_watcher's known public S3 URLs returned HTTP 403 this pass (see below) — this need still has no working live-tested source
