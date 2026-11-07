"""Port to an embedding model: texts in, one vector per text out (decision 2.6)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from regression_detector.ports.llm import Usage


class EmbeddingUnavailableError(Exception):
    """The provider could not answer after its retries (network, rate limit, server error)."""


@dataclass(frozen=True)
class EmbeddingResult:
    """Vectors in the same order as the input texts, plus what the call consumed."""

    vectors: tuple[tuple[float, ...], ...]
    requested_model: str
    served_model: str
    usage: Usage
    latency_ms: float


class EmbeddingClient(Protocol):
    """Anything that can turn texts into vectors."""

    async def embed(self, model: str, texts: Sequence[str]) -> EmbeddingResult: ...
