"""Port to an observability backend (planning §6): one experiment per run, one trace per case.

Scores are added by the scoring steps (6 and 8); the shape may be refined when the
Langfuse adapter is built (step 11).
"""

from typing import Any, Protocol

from regression_detector.eval.records import RunInfo, RunRecord
from regression_detector.ports.llm import LLMRequest, LLMResult


class Tracer(Protocol):
    """Anything that can record a run as an experiment."""

    def start_run(self, info: RunInfo) -> None: ...

    def record_case(
        self, case_id: str, request: LLMRequest[Any], result: LLMResult[Any]
    ) -> None: ...

    def finish_run(self, record: RunRecord) -> None: ...
