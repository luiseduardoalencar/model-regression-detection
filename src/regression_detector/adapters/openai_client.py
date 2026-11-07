"""OpenAI adapter for the LLM port: Responses API with structured output (decisions 1.5, 1.6)."""

import time
from typing import Any

import openai
from openai import AsyncOpenAI
from openai.lib._parsing._responses import type_to_text_format_param
from openai.types.responses import Response
from pydantic import BaseModel, ValidationError

from regression_detector.ports.llm import (
    LLMConfigurationError,
    LLMRequest,
    LLMResult,
    LLMStatus,
    Usage,
)

MAX_RETRIES = 4
TIMEOUT_SECONDS = 60.0

# HTTP errors the SDK does not retry: repeating the call can never fix them.
CONFIGURATION_ERRORS = (
    openai.BadRequestError,  # 400
    openai.AuthenticationError,  # 401
    openai.PermissionDeniedError,  # 403
    openai.NotFoundError,  # 404
    openai.UnprocessableEntityError,  # 422
)


def build_async_openai() -> AsyncOpenAI:
    """SDK client with the retry and timeout policy of decision 1.6; reads OPENAI_API_KEY."""
    try:
        return AsyncOpenAI(max_retries=MAX_RETRIES, timeout=TIMEOUT_SECONDS)
    except openai.OpenAIError as exc:
        raise LLMConfigurationError(str(exc)) from exc


class OpenAIClient:
    """Sends an `LLMRequest` to the OpenAI Responses API and maps the answer to `LLMResult`."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def complete[T: BaseModel](self, request: LLMRequest[T]) -> LLMResult[T]:
        started = time.perf_counter()
        try:
            response = await self._client.responses.create(**_request_arguments(request))
        except CONFIGURATION_ERRORS as exc:
            raise LLMConfigurationError(f"{type(exc).__name__}: {exc.message}") from exc
        except (openai.APIConnectionError, openai.APIStatusError) as exc:
            return LLMResult(
                status=LLMStatus.ERROR,
                parsed=None,
                raw_text=None,
                requested_model=request.model,
                served_model=None,
                usage=Usage(),
                latency_ms=_elapsed_ms(started),
                provider_request_id=getattr(exc, "request_id", None),
                detail=f"{type(exc).__name__}: {exc}",
            )
        return _to_result(request, response, _elapsed_ms(started))


def _request_arguments(request: LLMRequest[Any]) -> dict[str, Any]:
    """Translate the provider-neutral request into Responses API arguments."""
    arguments: dict[str, Any] = {
        "model": request.model,
        "instructions": request.instructions,
        "input": _input_messages(request),
        "text": {"format": type_to_text_format_param(request.output_schema)},
        "reasoning": {"effort": request.generation.reasoning_effort},
        "max_output_tokens": request.generation.max_output_tokens,
    }
    if request.generation.temperature is not None:
        arguments["temperature"] = request.generation.temperature
    return arguments


def _input_messages(request: LLMRequest[Any]) -> list[dict[str, str]]:
    """Few-shot examples as user/assistant turns, then the real input."""
    messages: list[dict[str, str]] = []
    for example in request.few_shot_examples:
        messages.append({"role": "user", "content": example.input_text})
        messages.append({"role": "assistant", "content": example.output_text})
    messages.append({"role": "user", "content": request.user_input})
    return messages


def _to_result[T: BaseModel](
    request: LLMRequest[T], response: Response, latency_ms: float
) -> LLMResult[T]:
    """Map a Responses API answer to one of the five statuses."""
    text, refusal = _final_answer(response)

    def result(status: LLMStatus, parsed: T | None = None, detail: str | None = None):
        return LLMResult(
            status=status,
            parsed=parsed,
            raw_text=text,
            requested_model=request.model,
            served_model=response.model,
            usage=_usage(response),
            latency_ms=latency_ms,
            provider_request_id=response._request_id,
            detail=detail,
        )

    if response.status == "incomplete":
        reason = response.incomplete_details.reason if response.incomplete_details else None
        return result(LLMStatus.INCOMPLETE, detail=reason)
    if response.status != "completed":
        message = response.error.message if response.error else None
        return result(LLMStatus.ERROR, detail=f"response status {response.status}: {message}")
    if refusal is not None:
        return result(LLMStatus.REFUSAL, detail=refusal)
    if not text:
        return result(LLMStatus.INVALID_OUTPUT, detail="empty output")
    try:
        parsed = request.output_schema.model_validate_json(text)
    except ValidationError as exc:
        return result(LLMStatus.INVALID_OUTPUT, detail=str(exc.errors()[0]["msg"]))
    return result(LLMStatus.COMPLETED, parsed=parsed)


def _final_answer(response: Response) -> tuple[str | None, str | None]:
    """Text and refusal of the final answer, skipping messages from other phases."""
    texts: list[str] = []
    refusal: str | None = None
    for item in response.output:
        if item.type != "message" or getattr(item, "phase", None) not in (None, "final_answer"):
            continue
        for content in item.content:
            if content.type == "output_text":
                texts.append(content.text)
            elif content.type == "refusal":
                refusal = content.refusal
    return ("".join(texts) or None), refusal


def _usage(response: Response) -> Usage:
    usage = response.usage
    if usage is None:
        return Usage()
    return Usage(
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.input_tokens_details.cached_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
