"""Tracer that records nothing: used in CI (Langfuse is local only) and in tests."""

from typing import Any

from regression_detector.eval.records import RunInfo, RunRecord
from regression_detector.ports.llm import LLMRequest, LLMResult


class NoopTracer:
    """Accepts every call of the `Tracer` port and does nothing."""

    def start_run(self, info: RunInfo) -> None:
        pass

    def record_case(self, case_id: str, request: LLMRequest[Any], result: LLMResult[Any]) -> None:
        pass

    def finish_run(self, record: RunRecord) -> None:
        pass
