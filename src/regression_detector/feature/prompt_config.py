"""Contents of a classifier prompt file, `prompts/classifier/vN.yaml` (decisions 1.2-1.4)."""

from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from regression_detector.feature.models import Category
from regression_detector.ports.llm import GenerationParams

CATEGORIES_PLACEHOLDER = "{categories}"
TIE_BREAK_RULES_PLACEHOLDER = "{tie_break_rules}"
PLACEHOLDERS = (CATEGORIES_PLACEHOLDER, TIE_BREAK_RULES_PLACEHOLDER)

NonEmptyText = Annotated[str, Field(min_length=1)]

# The only reasoning effort that accepts temperature (OpenAI GPT-6 guide, planning §3).
EFFORT_WITH_SAMPLING = "none"


class Generation(BaseModel):
    """How each output token is drawn: the `generation` block of the prompt file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reasoning_effort: str = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int = Field(gt=0)

    @model_validator(mode="after")
    def temperature_only_without_reasoning(self) -> Self:
        if self.temperature is not None and self.reasoning_effort != EFFORT_WITH_SAMPLING:
            raise ValueError(
                f"temperature is only accepted with reasoning_effort {EFFORT_WITH_SAMPLING!r}"
            )
        return self

    def to_params(self) -> GenerationParams:
        return GenerationParams(
            reasoning_effort=self.reasoning_effort,
            max_output_tokens=self.max_output_tokens,
            temperature=self.temperature,
        )


class FewShotCase(BaseModel):
    """One example shown to the model before the real email (decision 1.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=1)
    category: Category
    summary: str = Field(min_length=1)


class PromptConfig(BaseModel):
    """The full runtime contract of one classifier prompt version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version_id: str = Field(pattern=r"^v\d+$")
    created_at: date
    change_note: str = Field(min_length=1)
    model: str = Field(min_length=1)
    generation: Generation
    categories: dict[Category, NonEmptyText]
    tie_break_rules: list[NonEmptyText] = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    few_shot_examples: list[FewShotCase] = Field(min_length=1)

    @model_validator(mode="after")
    def categories_match_the_enum(self) -> Self:
        if list(self.categories) != list(Category):
            raise ValueError("categories must define every Category label, in enum order")
        return self

    @model_validator(mode="after")
    def placeholders_appear_once(self) -> Self:
        for placeholder in PLACEHOLDERS:
            count = self.system_prompt.count(placeholder)
            if count != 1:
                raise ValueError(f"system_prompt must contain {placeholder} once, found {count}")
        return self
