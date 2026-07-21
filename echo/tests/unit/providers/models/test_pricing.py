from providers.models.claude.pricing import estimate_cost_usd


def test_known_model_uses_its_own_price() -> None:
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 12.0  # $2 input + $10 output per million, verified 2026-07-21


def test_unknown_model_falls_back_to_default_price() -> None:
    cost = estimate_cost_usd("some-future-model", input_tokens=1_000_000, output_tokens=0)
    assert cost == 3.0


def test_zero_tokens_costs_nothing() -> None:
    assert estimate_cost_usd("claude-haiku-4-5", input_tokens=0, output_tokens=0) == 0.0


def test_none_tokens_treated_as_zero() -> None:
    assert estimate_cost_usd("claude-opus-4-8", input_tokens=None, output_tokens=None) == 0.0
