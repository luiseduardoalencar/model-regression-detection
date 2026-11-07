"""OpenAI adapter for the embedding port (decision 2.6), same failure policy as decision 1.6."""

import time
from collections.abc import Sequence

import openai
from openai import AsyncOpenAI

from regression_detector.adapters.openai_client import CONFIGURATION_ERRORS
from regression_detector.ports.embeddings import EmbeddingResult, EmbeddingUnavailableError
from regression_detector.ports.llm import LLMConfigurationError, Usage

MAX_INPUTS_PER_REQUEST = 2048


class OpenAIEmbeddingClient:
    """Sends texts to the OpenAI embeddings endpoint in one request."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def embed(self, model: str, texts: Sequence[str]) -> EmbeddingResult:
        if not texts or len(texts) > MAX_INPUTS_PER_REQUEST:
            raise ValueError(f"send between 1 and {MAX_INPUTS_PER_REQUEST} texts per request")
        started = time.perf_counter()
        try:
            response = await self._client.embeddings.create(
                model=model, input=list(texts), encoding_format="float"
            )
        except CONFIGURATION_ERRORS as exc:
            raise LLMConfigurationError(f"{type(exc).__name__}: {exc.message}") from exc
        except (openai.APIConnectionError, openai.APIStatusError) as exc:
            raise EmbeddingUnavailableError(f"{type(exc).__name__}: {exc}") from exc

        ordered = sorted(response.data, key=lambda item: item.index)
        return EmbeddingResult(
            vectors=tuple(tuple(item.embedding) for item in ordered),
            requested_model=model,
            served_model=response.model,
            usage=Usage(input_tokens=response.usage.prompt_tokens),
            latency_ms=(time.perf_counter() - started) * 1000,
        )
