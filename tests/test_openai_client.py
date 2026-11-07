"""OpenAIClient against simulated HTTP answers: no network, no cost."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from regression_detector.adapters.openai_client import (
    MAX_RETRIES,
    TIMEOUT_SECONDS,
    OpenAIClient,
    build_async_openai,
)
from regression_detector.feature.models import Category, EmailClassification
from regression_detector.ports.llm import (
    FewShotExample,
    GenerationParams,
    LLMConfigurationError,
    LLMRequest,
    LLMStatus,
)

pytestmark = pytest.mark.asyncio

VALID_ANSWER = '{"category": "delivery", "summary": "Cliente pergunta pelo pedido atrasado."}'


def make_request(**changes) -> LLMRequest[EmailClassification]:
    fields = {
        "model": "gpt-6-luna",
        "instructions": "Classifique o email.",
        "user_input": "Meu pedido não chegou.",
        "output_schema": EmailClassification,
        "generation": GenerationParams(
            reasoning_effort="none", max_output_tokens=200, temperature=0.0
        ),
    }
    fields.update(changes)
    return LLMRequest(**fields)


def response_body(
    *,
    status: str = "completed",
    content: list[dict] | None = None,
    incomplete_reason: str | None = None,
) -> dict:
    if content is None:
        content = [{"type": "output_text", "text": VALID_ANSWER, "annotations": []}]
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1_794_000_000,
        "model": "gpt-6-luna-2026-10-05",
        "status": status,
        "error": None,
        "incomplete_details": {"reason": incomplete_reason} if incomplete_reason else None,
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "role": "assistant",
                "status": status,
                "content": content,
            }
        ],
        "usage": {
            "input_tokens": 300,
            "input_tokens_details": {"cached_tokens": 100},
            "output_tokens": 40,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 340,
        },
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
    }


class FakeOpenAI:
    """Answers every HTTP request with the next prepared response and records the calls."""

    def __init__(self, *answers: httpx.Response | Exception) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def client(self, max_retries: int = 0) -> OpenAIClient:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        sdk = AsyncOpenAI(api_key="test-key", max_retries=max_retries, http_client=http_client)
        return OpenAIClient(sdk)


def ok(body: dict) -> httpx.Response:
    return httpx.Response(200, json=body, headers={"x-request-id": "req_test"})


def http_error(status_code: int) -> httpx.Response:
    # retry-after-ms keeps the SDK's wait between retries at 1 ms in tests
    return httpx.Response(
        status_code,
        json={"error": {"message": "simulated", "type": "test", "code": None}},
        headers={"retry-after-ms": "1"},
    )


async def test_completed_answer_is_parsed():
    fake = FakeOpenAI(ok(response_body()))
    result = await fake.client().complete(make_request())

    assert result.status is LLMStatus.COMPLETED
    assert result.parsed == EmailClassification(
        category=Category.DELIVERY, summary="Cliente pergunta pelo pedido atrasado."
    )
    assert result.raw_text == VALID_ANSWER
    assert result.requested_model == "gpt-6-luna"
    assert result.served_model == "gpt-6-luna-2026-10-05"
    assert result.provider_request_id == "req_test"
    assert result.usage.input_tokens == 300
    assert result.usage.cached_input_tokens == 100
    assert result.usage.output_tokens == 40
    assert result.latency_ms >= 0


async def test_request_carries_prompt_examples_and_strict_schema():
    fake = FakeOpenAI(ok(response_body()))
    example = FewShotExample(
        input_text="Quero cancelar.", output_text='{"category": "cancellation"}'
    )
    await fake.client().complete(make_request(few_shot_examples=(example,)))

    sent = json.loads(fake.requests[0].content)
    assert sent["model"] == "gpt-6-luna"
    assert sent["instructions"] == "Classifique o email."
    assert sent["input"] == [
        {"role": "user", "content": "Quero cancelar."},
        {"role": "assistant", "content": '{"category": "cancellation"}'},
        {"role": "user", "content": "Meu pedido não chegou."},
    ]
    assert sent["text"]["format"]["type"] == "json_schema"
    assert sent["text"]["format"]["strict"] is True
    assert sent["reasoning"] == {"effort": "none"}
    assert sent["max_output_tokens"] == 200
    assert sent["temperature"] == 0.0


async def test_temperature_is_omitted_when_not_set():
    fake = FakeOpenAI(ok(response_body()))
    generation = GenerationParams(reasoning_effort="low", max_output_tokens=200)
    await fake.client().complete(make_request(generation=generation))

    assert "temperature" not in json.loads(fake.requests[0].content)


async def test_refusal_is_reported_and_not_parsed():
    refusal = [{"type": "refusal", "refusal": "Não posso ajudar com isso."}]
    fake = FakeOpenAI(ok(response_body(content=refusal)))
    result = await fake.client().complete(make_request())

    assert result.status is LLMStatus.REFUSAL
    assert result.parsed is None
    assert result.detail == "Não posso ajudar com isso."


async def test_truncated_answer_is_incomplete_and_keeps_usage():
    truncated = [{"type": "output_text", "text": '{"category": "deliv', "annotations": []}]
    body = response_body(
        status="incomplete", content=truncated, incomplete_reason="max_output_tokens"
    )
    result = await FakeOpenAI(ok(body)).client().complete(make_request())

    assert result.status is LLMStatus.INCOMPLETE
    assert result.detail == "max_output_tokens"
    assert result.raw_text == '{"category": "deliv'
    assert result.usage.output_tokens == 40


@pytest.mark.parametrize(
    "text",
    [
        '{"category": "spam", "summary": "x"}',
        '{"category": "delivery"}',
        "not json",
    ],
)
async def test_answer_outside_the_schema_is_invalid_output(text):
    content = [{"type": "output_text", "text": text, "annotations": []}]
    result = await FakeOpenAI(ok(response_body(content=content))).client().complete(make_request())

    assert result.status is LLMStatus.INVALID_OUTPUT
    assert result.parsed is None
    assert result.raw_text == text


async def test_rate_limit_is_retried_until_exhausted_then_error():
    fake = FakeOpenAI(http_error(429))
    result = await fake.client(max_retries=2).complete(make_request())

    assert result.status is LLMStatus.ERROR
    assert len(fake.requests) == 3
    assert result.usage.input_tokens == 0


async def test_server_error_followed_by_success_completes():
    fake = FakeOpenAI(http_error(500), ok(response_body()))
    result = await fake.client(max_retries=2).complete(make_request())

    assert result.status is LLMStatus.COMPLETED
    assert len(fake.requests) == 2


async def test_connection_failure_is_an_infrastructure_error():
    fake = FakeOpenAI(httpx.ConnectError("network down"))
    result = await fake.client(max_retries=1).complete(make_request())

    assert result.status is LLMStatus.ERROR
    assert len(fake.requests) == 2


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
async def test_configuration_errors_stop_the_run_without_retry(status_code):
    fake = FakeOpenAI(http_error(status_code))
    with pytest.raises(LLMConfigurationError):
        await fake.client(max_retries=2).complete(make_request())

    assert len(fake.requests) == 1


async def test_sdk_client_uses_the_decided_retry_policy(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    sdk = build_async_openai()

    assert sdk.max_retries == MAX_RETRIES == 4
    assert sdk.timeout == TIMEOUT_SECONDS == 60.0


async def test_missing_api_key_is_a_configuration_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError):
        build_async_openai()
