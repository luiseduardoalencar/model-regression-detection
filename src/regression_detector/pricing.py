"""Cost of an LLM call from its token usage and the versioned price table (decision 1.5)."""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from regression_detector.ports.llm import LLMConfigurationError, Usage

DEFAULT_PRICING_PATH = Path("config/pricing.yaml")
TOKENS_PER_PRICE_UNIT = 1_000_000


class ModelPrice(BaseModel):
    """Prices of one model in US$ per 1M tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: float = Field(ge=0)
    cached_input: float = Field(ge=0)
    output: float = Field(ge=0)


class PriceTable(BaseModel):
    """The contents of `config/pricing.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checked_on: date
    source: str
    models: dict[str, ModelPrice]

    def price_for(self, model: str) -> ModelPrice:
        """Return the model's prices; a missing model stops the run instead of costing zero."""
        price = self.models.get(model)
        if price is None:
            raise LLMConfigurationError(f"model {model!r} has no price in the price table")
        return price

    def cost_usd(self, model: str, usage: Usage) -> float:
        """Cost of one call; cached tokens are part of input, reasoning tokens part of output."""
        price = self.price_for(model)
        uncached_input = usage.input_tokens - usage.cached_input_tokens
        total = (
            uncached_input * price.input
            + usage.cached_input_tokens * price.cached_input
            + usage.output_tokens * price.output
        )
        return total / TOKENS_PER_PRICE_UNIT


def load_price_table(path: Path = DEFAULT_PRICING_PATH) -> PriceTable:
    """Read and validate the price table."""
    with path.open(encoding="utf-8") as file:
        return PriceTable.model_validate(yaml.safe_load(file))
