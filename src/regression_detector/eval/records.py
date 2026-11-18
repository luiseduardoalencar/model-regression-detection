"""What one eval run produces: one record per case and one per run (planning §6, decision 1.6)."""

from dataclasses import dataclass
from datetime import datetime

from regression_detector.eval.validity import RunValidity
from regression_detector.feature.models import Category
from regression_detector.ports.llm import LLMStatus, Usage


@dataclass(frozen=True)
class GoldenRef:
    """Which golden edition a run used: number, draft or frozen, and the file's sha256."""

    edition: int
    status: str
    sha256: str


@dataclass(frozen=True)
class CaseResult:
    """The classifier's answer to one golden case, with what the call cost and how it ended."""

    case_id: str
    status: LLMStatus
    category: Category | None
    summary: str | None
    raw_text: str | None
    requested_model: str
    served_model: str | None
    usage: Usage
    cost_usd: float
    latency_ms: float
    provider_request_id: str | None
    from_local_cache: bool
    detail: str | None

    @property
    def spent_usd(self) -> float:
        """What this run paid for the case: nothing when the answer came from the local cache."""
        return 0.0 if self.from_local_cache else self.cost_usd


@dataclass(frozen=True)
class RunInfo:
    """The identity of a run, known before the first call."""

    run_id: str
    started_at: datetime
    prompt_version_id: str
    prompt_sha256: str
    model: str
    golden: GoldenRef


@dataclass(frozen=True)
class RunRecord:
    """A finished run: identity, validity and every case result, in golden order."""

    info: RunInfo
    finished_at: datetime
    validity: RunValidity
    infra_errors: int
    cases: tuple[CaseResult, ...]

    @property
    def run_id(self) -> str:
        return self.info.run_id

    @property
    def exam_cost_usd(self) -> float:
        """What the whole exam costs without the local cache: the number to compare runs by."""
        return sum(case.cost_usd for case in self.cases)

    @property
    def spent_usd(self) -> float:
        """What this run actually paid; cases answered from the local cache cost nothing."""
        return sum(case.spent_usd for case in self.cases)
