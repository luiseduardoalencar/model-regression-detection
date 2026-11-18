"""In-memory fakes of the ports, so the eval engine is tested without network or cost."""

import asyncio
from typing import Any

from regression_detector.eval.records import RunInfo, RunRecord
from regression_detector.feature.classifier import EMAIL_CLOSE, EMAIL_OPEN
from regression_detector.feature.models import Category, EmailClassification
from regression_detector.ports.llm import (
    LLMConfigurationError,
    LLMRequest,
    LLMResult,
    LLMStatus,
    Usage,
)

FAKE_USAGE = Usage(input_tokens=2000, cached_input_tokens=1500, output_tokens=40)
FAKE_SERVED_MODEL = "gpt-6-luna-2026-10-01"
BROKEN_TEXT = {LLMStatus.INVALID_OUTPUT, LLMStatus.INCOMPLETE}


def email_of(request: LLMRequest[Any]) -> str:
    """The email inside the `<email>` delimiters of the request."""
    return request.user_input.removeprefix(f"{EMAIL_OPEN}\n").removesuffix(f"\n{EMAIL_CLOSE}")


class FakeLLMClient:
    """Answers `general` for every email, except the ones scripted to end otherwise.

    `outcomes` maps an email to the status its call ends with; `config_error` holds emails
    whose call raises `LLMConfigurationError`; `delays` maps an email to seconds of waiting.
    """

    def __init__(
        self,
        outcomes: dict[str, LLMStatus] | None = None,
        *,
        config_error: set[str] | None = None,
        delays: dict[str, float] | None = None,
        default_delay: float = 0.0,
    ) -> None:
        self.outcomes = outcomes or {}
        self.config_error = config_error or set()
        self.delays = delays or {}
        self.default_delay = default_delay
        self.requests: list[LLMRequest[Any]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def complete(self, request: LLMRequest[Any]) -> LLMResult[Any]:
        self.requests.append(request)
        email = email_of(request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delays.get(email, self.default_delay))
        finally:
            self.in_flight -= 1
        if email in self.config_error:
            raise LLMConfigurationError("NotFoundError: model not found")
        return fake_result(request, self.outcomes.get(email, LLMStatus.COMPLETED))


def fake_result(request: LLMRequest[Any], status: LLMStatus) -> LLMResult[Any]:
    """An `LLMResult` shaped like the OpenAI adapter's for the given status."""
    if status == LLMStatus.COMPLETED:
        parsed = EmailClassification(category=Category.GENERAL, summary="Cliente pede ajuda.")
        return LLMResult(
            status=status,
            parsed=parsed,
            raw_text=parsed.model_dump_json(),
            requested_model=request.model,
            served_model=FAKE_SERVED_MODEL,
            usage=FAKE_USAGE,
            latency_ms=850.0,
            provider_request_id="req_fake",
        )
    infra = status == LLMStatus.ERROR
    # Like the OpenAI adapter: invalid and cut answers keep the text the model wrote.
    broken_text = '{"category": "delivery", "summ' if status in BROKEN_TEXT else None
    return LLMResult(
        status=status,
        parsed=None,
        raw_text=broken_text,
        requested_model=request.model,
        served_model=None if infra else FAKE_SERVED_MODEL,
        usage=Usage() if infra else FAKE_USAGE,
        latency_ms=60_000.0 if infra else 900.0,
        provider_request_id=None if infra else "req_fake",
        detail=f"fake {status}",
    )


class RecordingTracer:
    """Keeps every call of the `Tracer` port for the tests to inspect."""

    def __init__(self) -> None:
        self.started: list[RunInfo] = []
        self.cases: list[tuple[str, LLMRequest[Any], LLMResult[Any]]] = []
        self.finished: list[RunRecord] = []

    def start_run(self, info: RunInfo) -> None:
        self.started.append(info)

    def record_case(self, case_id: str, request: LLMRequest[Any], result: LLMResult[Any]) -> None:
        self.cases.append((case_id, request, result))

    def finish_run(self, record: RunRecord) -> None:
        self.finished.append(record)
