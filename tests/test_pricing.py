from pathlib import Path

import pytest
from pydantic import ValidationError

from regression_detector.ports.llm import LLMConfigurationError, Usage
from regression_detector.pricing import ModelPrice, PriceTable, load_price_table

TABLE = PriceTable(
    checked_on="2026-11-06",
    source="test",
    models={"model-a": ModelPrice(input=0.10, cached_input=0.01, output=0.50)},
)


def test_versioned_price_table_loads():
    table = load_price_table(Path("config/pricing.yaml"))
    assert {"gpt-6-luna", "gpt-6.1-terra"} <= table.models.keys()


def test_cost_without_cache():
    usage = Usage(input_tokens=1_000, output_tokens=100)
    # 1000 x 0.10 + 100 x 0.50 = 150 per 1M tokens
    assert TABLE.cost_usd("model-a", usage) == pytest.approx(150 / 1_000_000)


def test_cached_tokens_are_charged_at_the_cached_price():
    usage = Usage(input_tokens=1_000, cached_input_tokens=200, output_tokens=100)
    # 800 x 0.10 + 200 x 0.01 + 100 x 0.50 = 132 per 1M tokens
    assert TABLE.cost_usd("model-a", usage) == pytest.approx(132 / 1_000_000)


def test_reasoning_tokens_are_not_charged_twice():
    without = Usage(input_tokens=1_000, output_tokens=100)
    with_reasoning = Usage(input_tokens=1_000, output_tokens=100, reasoning_tokens=60)
    assert TABLE.cost_usd("model-a", with_reasoning) == TABLE.cost_usd("model-a", without)


def test_model_missing_from_the_table_stops_the_run():
    with pytest.raises(LLMConfigurationError, match="model-b"):
        TABLE.cost_usd("model-b", Usage())


@pytest.mark.parametrize(
    "price",
    [
        {"input": -0.1, "cached_input": 0.01, "output": 0.5},
        {"input": 0.1, "output": 0.5},
        {"input": 0.1, "cached_input": 0.01, "output": 0.5, "batch": 0.05},
    ],
)
def test_invalid_prices_are_rejected(price):
    with pytest.raises(ValidationError):
        ModelPrice.model_validate(price)
