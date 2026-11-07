"""Port to a large language model (decision 1.5): one async call, one standard result."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class LLMStatus(StrEnum):
    """How a call ended: only `completed` carries a usable answer."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    REFUSAL = "refusal"
    INVALID_OUTPUT = "invalid_output"
    ERROR = "error"


class LLMConfigurationError(Exception):
    """The request can never succeed as configured; the whole run must stop."""


@dataclass(frozen=True)
class GenerationParams:
    """Generation parameters from the prompt file (decision 1.2)."""

    reasoning_effort: str
    max_output_tokens: int
    temperature: float | None = None


@dataclass(frozen=True)
class FewShotExample:
    """One example exchange shown to the model before the real input."""

    input_text: str
    output_text: str


@dataclass(frozen=True)
class LLMRequest[T: BaseModel]:
    """Everything the model needs for one call, independent of the provider."""

    model: str
    instructions: str
    user_input: str
    output_schema: type[T]
    generation: GenerationParams
    few_shot_examples: tuple[FewShotExample, ...] = ()


@dataclass(frozen=True)
class Usage:
    """Token counts; cached tokens are part of input, reasoning tokens part of output."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    """What came back from one call, whatever its status."""

    status: LLMStatus
    parsed: T | None
    raw_text: str | None
    requested_model: str
    served_model: str | None
    usage: Usage
    latency_ms: float
    provider_request_id: str | None
    detail: str | None = None


class LLMClient(Protocol):
    """Anything that can send an `LLMRequest` to a model and return an `LLMResult`."""

    async def complete[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]: ...
