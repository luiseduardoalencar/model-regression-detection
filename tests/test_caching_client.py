"""The local response cache: what the key covers, what is stored, expiry and bypass."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from regression_detector.adapters.caching_client import (
    CachingLLMClient,
    SQLiteResponseCache,
    request_key,
)
from regression_detector.feature.classifier import build_request
from regression_detector.feature.prompt_config import PromptConfig
from regression_detector.ports.llm import (
    FewShotExample,
    GenerationParams,
    LLMConfigurationError,
    LLMStatus,
)
from tests.factories import prompt_data
from tests.fakes import FAKE_USAGE, FakeLLMClient

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
EMAIL = "Meu pedido 333 não chegou."


def request(email: str = EMAIL):
    return build_request(PromptConfig.model_validate(prompt_data()), email)


class OtherSchema(BaseModel):
    category: str


def test_the_key_is_versioned_and_stable():
    key = request_key(request())
    assert key.startswith("v1:")
    assert len(key) == len("v1:") + 64
    assert request_key(request()) == key


@pytest.mark.parametrize(
    "change",
    [
        {"model": "gpt-6.1-terra"},
        {"instructions": "Outras instruções."},
        {"user_input": "<email>\noutro\n</email>"},
        {"few_shot_examples": (FewShotExample("<email>\nx\n</email>", "{}"),)},
        {"output_schema": OtherSchema},
        {"generation": GenerationParams("none", 200, 0.5)},
        {"generation": GenerationParams("none", 300, 0)},
        {"generation": GenerationParams("low", 200)},
    ],
)
def test_any_change_in_what_the_model_receives_changes_the_key(change):
    original = request()
    assert request_key(replace(original, **change)) != request_key(original)


def caching(client, tmp_path, *, now=T0, ttl=timedelta(days=7), bypass=False):
    cache = SQLiteResponseCache(tmp_path / "cache.sqlite", ttl=ttl)
    return CachingLLMClient(client, cache, bypass=bypass, clock=lambda: now), cache


def test_a_completed_call_is_served_from_the_cache_the_second_time(tmp_path):
    inner = FakeLLMClient()
    client, cache = caching(inner, tmp_path)
    first = asyncio.run(client.complete(request()))
    second = asyncio.run(client.complete(request()))
    cache.close()
    assert len(inner.requests) == 1
    assert first.from_local_cache is False
    assert second.from_local_cache is True
    assert second.status == LLMStatus.COMPLETED
    assert second.parsed == first.parsed
    assert second.raw_text == first.raw_text
    # Usage and latency of the original call, so tokens and latency stay comparable.
    assert second.usage == FAKE_USAGE == first.usage
    assert second.latency_ms == first.latency_ms
    assert second.served_model == first.served_model


def test_the_cache_survives_reopening_the_file(tmp_path):
    inner = FakeLLMClient()
    client, cache = caching(inner, tmp_path)
    asyncio.run(client.complete(request()))
    cache.close()
    reopened, cache = caching(inner, tmp_path)
    assert asyncio.run(reopened.complete(request())).from_local_cache is True
    cache.close()
    assert len(inner.requests) == 1


@pytest.mark.parametrize(
    "status",
    [LLMStatus.ERROR, LLMStatus.REFUSAL, LLMStatus.INCOMPLETE, LLMStatus.INVALID_OUTPUT],
)
def test_only_completed_calls_are_stored(tmp_path, status):
    inner = FakeLLMClient(outcomes={EMAIL: status})
    client, cache = caching(inner, tmp_path)
    asyncio.run(client.complete(request()))
    result = asyncio.run(client.complete(request()))
    stored = cache._connection.execute("SELECT count(*) FROM responses").fetchone()[0]
    cache.close()
    assert stored == 0
    assert len(inner.requests) == 2
    assert result.from_local_cache is False


def test_an_entry_older_than_the_ttl_is_a_miss_and_is_refreshed(tmp_path):
    inner = FakeLLMClient()
    client, cache = caching(inner, tmp_path, now=T0)
    asyncio.run(client.complete(request()))
    cache.close()
    later, cache = caching(inner, tmp_path, now=T0 + timedelta(days=7, seconds=1))
    assert asyncio.run(later.complete(request())).from_local_cache is False
    assert asyncio.run(later.complete(request())).from_local_cache is True
    cache.close()
    assert len(inner.requests) == 2


def test_an_entry_within_the_ttl_is_a_hit(tmp_path):
    inner = FakeLLMClient()
    client, cache = caching(inner, tmp_path, now=T0)
    asyncio.run(client.complete(request()))
    cache.close()
    later, cache = caching(inner, tmp_path, now=T0 + timedelta(days=7))
    assert asyncio.run(later.complete(request())).from_local_cache is True
    cache.close()


def test_bypass_neither_reads_nor_writes(tmp_path):
    inner = FakeLLMClient()
    client, cache = caching(inner, tmp_path)
    asyncio.run(client.complete(request()))  # stored
    bypassing = CachingLLMClient(inner, cache, bypass=True, clock=lambda: T0)
    assert asyncio.run(bypassing.complete(request())).from_local_cache is False
    assert asyncio.run(bypassing.complete(request("Outro email."))).from_local_cache is False
    assert asyncio.run(client.complete(request("Outro email."))).from_local_cache is False
    cache.close()
    assert len(inner.requests) == 4


def test_a_configuration_error_propagates_and_stores_nothing(tmp_path):
    inner = FakeLLMClient(config_error={EMAIL})
    client, cache = caching(inner, tmp_path)
    with pytest.raises(LLMConfigurationError):
        asyncio.run(client.complete(request()))
    count = cache._connection.execute("SELECT count(*) FROM responses").fetchone()[0]
    cache.close()
    assert count == 0


def test_put_refuses_a_call_that_did_not_complete(tmp_path):
    inner = FakeLLMClient(outcomes={EMAIL: LLMStatus.REFUSAL})
    result = asyncio.run(inner.complete(request()))
    with SQLiteResponseCache(tmp_path / "cache.sqlite") as cache:
        with pytest.raises(ValueError):
            cache.put("v1:x", result, T0)
