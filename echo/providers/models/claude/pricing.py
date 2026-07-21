"""Per-token pricing, verified against Anthropic's own pricing page and
model-announcement posts on 2026-07-21 (CONSTITUTION.md: Provider Due
Diligence — "Claims regarding provider pricing... SHALL be verified before
becoming architectural assumptions. Marketing material shall not be
treated as authoritative technical documentation" — these figures came
from anthropic.com directly, not third-party claims).

Sonnet 5's introductory price expires 2026-08-31 and reverts to $3/$15 —
this table must be re-verified and updated at that point (tracked,
time-bounded technical debt per CONSTITUTION.md's Technical Debt section,
not an oversight).
"""

from __future__ import annotations

# (input_price_per_million_tokens_usd, output_price_per_million_tokens_usd)
PRICE_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.0, 10.0),  # introductory price; $3/$15 from 2026-08-31
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-4-8": (5.0, 25.0),
}

_DEFAULT_PRICE = (3.0, 15.0)  # Sonnet-tier fallback for an unrecognized model name


def estimate_cost_usd(
    model_name: str, input_tokens: int | None, output_tokens: int | None
) -> float:
    input_price, output_price = PRICE_PER_MILLION_TOKENS.get(model_name, _DEFAULT_PRICE)
    input_cost = (input_tokens or 0) / 1_000_000 * input_price
    output_cost = (output_tokens or 0) / 1_000_000 * output_price
    return round(input_cost + output_cost, 6)
