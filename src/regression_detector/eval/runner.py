"""The exam: every golden case through the classifier, concurrently, under a limit (decision 1.6).

The runner sends only the email and the prompt; the answer key never leaves the golden
case. Infrastructure errors are counted for run validity; a configuration error stops
the whole run (decision 1.6b).
"""

import asyncio
import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from regression_detector.eval.records import CaseResult, GoldenRef, RunInfo, RunRecord
from regression_detector.eval.validity import assess_validity
from regression_detector.feature.classifier import build_request
from regression_detector.feature.models import EmailClassification
from regression_detector.golden.schema import GoldenCase, GoldenEdition
from regression_detector.ports.llm import (
    LLMClient,
    LLMConfigurationError,
    LLMResult,
    LLMStatus,
)
from regression_detector.ports.tracer import Tracer
from regression_detector.pricing import PriceTable
from regression_detector.prompts.loader import LoadedPrompt

# Calls in flight at once (Inspect AI's default max_connections; decided 2026-11-17).
DEFAULT_CONCURRENCY = 10


def utc_now() -> datetime:
    return datetime.now(UTC)


def load_golden(path: Path) -> tuple[GoldenEdition, GoldenRef]:
    """Read an edition file once: the validated cases and the identity a run records."""
    raw = path.read_bytes()
    edition = GoldenEdition.model_validate_json(raw)
    ref = GoldenRef(
        edition=edition.edition, status=edition.status, sha256=hashlib.sha256(raw).hexdigest()
    )
    return edition, ref


async def run_exam(
    *,
    edition: GoldenEdition,
    golden: GoldenRef,
    prompt: LoadedPrompt,
    client: LLMClient,
    prices: PriceTable,
    tracer: Tracer,
    concurrency: int = DEFAULT_CONCURRENCY,
    clock: Callable[[], datetime] = utc_now,
) -> RunRecord:
    """Classify every case and return the run with its validity; results keep golden order."""
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    model = prompt.config.model
    prices.price_for(model)  # a model without a price stops the run before any call
    info = RunInfo(
        run_id=uuid.uuid4().hex,
        started_at=clock(),
        prompt_version_id=prompt.version_id,
        prompt_sha256=prompt.sha256,
        model=model,
        golden=golden,
    )
    tracer.start_run(info)
    limit = asyncio.Semaphore(concurrency)

    async def run_case(case: GoldenCase) -> CaseResult:
        request = build_request(prompt.config, case.input_email)
        async with limit:
            result = await client.complete(request)
        tracer.record_case(case.id, request, result)
        return _case_result(case.id, result, prices)

    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(run_case(case)) for case in edition.cases]
    except ExceptionGroup as errors:
        # TaskGroup has already cancelled the other calls; surface the configuration error.
        configuration = errors.subgroup(LLMConfigurationError)
        if configuration is not None:
            raise configuration.exceptions[0] from None
        raise

    cases = tuple(task.result() for task in tasks)
    infra_errors = sum(case.status == LLMStatus.ERROR for case in cases)
    validity = assess_validity(infra_errors, len(cases))
    record = RunRecord(
        info=info,
        finished_at=clock(),
        validity=validity.validity,
        infra_errors=infra_errors,
        cases=cases,
    )
    tracer.finish_run(record)
    return record


def _case_result(
    case_id: str, result: LLMResult[EmailClassification], prices: PriceTable
) -> CaseResult:
    parsed = result.parsed
    return CaseResult(
        case_id=case_id,
        status=result.status,
        category=parsed.category if parsed is not None else None,
        summary=parsed.summary if parsed is not None else None,
        raw_text=result.raw_text,
        requested_model=result.requested_model,
        served_model=result.served_model,
        usage=result.usage,
        cost_usd=prices.cost_usd(result.requested_model, result.usage),
        latency_ms=result.latency_ms,
        provider_request_id=result.provider_request_id,
        from_local_cache=result.from_local_cache,
        detail=result.detail,
    )
