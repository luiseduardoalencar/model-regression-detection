"""OpenAIEmbeddingClient against simulated HTTP answers: no network, no cost."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from regression_detector.adapters.openai_embeddings import OpenAIEmbeddingClient
from regression_detector.ports.embeddings import EmbeddingUnavailableError
from regression_detector.ports.llm import LLMConfigurationError

pytestmark = pytest.mark.asyncio


def embeddings_body(order: list[int]) -> dict:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": index, "embedding": [float(index), 1.0]}
            for index in order
        ],
        "model": "text-embedding-3-large",
        "usage": {"prompt_tokens": 12, "total_tokens": 12},
    }


def client_answering(*answers: httpx.Response, max_retries: int = 0):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return answers[min(len(requests), len(answers)) - 1]

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncOpenAI(api_key="test-key", max_retries=max_retries, http_client=http_client)
    return OpenAIEmbeddingClient(sdk), requests


def http_error(status_code: int) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"error": {"message": "simulated", "type": "test", "code": None}},
        headers={"retry-after-ms": "1"},
    )


async def test_vectors_come_back_in_input_order():
    client, requests = client_answering(httpx.Response(200, json=embeddings_body([2, 0, 1])))
    result = await client.embed("text-embedding-3-large", ["a", "b", "c"])

    assert result.vectors == ((0.0, 1.0), (1.0, 1.0), (2.0, 1.0))
    assert result.usage.input_tokens == 12
    assert result.served_model == "text-embedding-3-large"
    sent = json.loads(requests[0].content)
    assert sent == {
        "model": "text-embedding-3-large",
        "input": ["a", "b", "c"],
        "encoding_format": "float",
    }


async def test_configuration_error_stops_without_retry():
    client, requests = client_answering(http_error(401), max_retries=2)
    with pytest.raises(LLMConfigurationError):
        await client.embed("text-embedding-3-large", ["a"])
    assert len(requests) == 1


async def test_rate_limit_after_retries_means_unavailable():
    client, requests = client_answering(http_error(429), max_retries=2)
    with pytest.raises(EmbeddingUnavailableError):
        await client.embed("text-embedding-3-large", ["a"])
    assert len(requests) == 3


@pytest.mark.parametrize("count", [0, 2049])
async def test_batch_size_outside_the_api_limits_is_refused(count):
    client, requests = client_answering(httpx.Response(200, json=embeddings_body([0])))
    with pytest.raises(ValueError):
        await client.embed("text-embedding-3-large", ["a"] * count)
    assert requests == []
