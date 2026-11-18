"""Per-case scoring (decisions 1.6, 3.1 and 3.4): category outcome, format checks, numbers.

Scores are recomputed from the stored answers and the golden set, never stored, so the
baseline and the candidate of a comparison are always scored by the same code
(decided 2026-11-17).
"""

from dataclasses import dataclass
from enum import StrEnum

from regression_detector.eval.format_checks import FormatResult, check_format
from regression_detector.eval.records import CaseResult, RunRecord
from regression_detector.feature.models import Category
from regression_detector.golden.schema import EdgeType, GoldenCase, GoldenEdition
from regression_detector.ports.llm import LLMStatus

NO_ANSWER_STATUSES = frozenset({LLMStatus.REFUSAL, LLMStatus.INCOMPLETE, LLMStatus.INVALID_OUTPUT})


class CategoryOutcome(StrEnum):
    """How the predicted category compares with the answer key."""

    EXACT = "exact"
    ACCEPTABLE = "acceptable"
    MISS = "miss"
    NO_ANSWER = "no_answer"


@dataclass(frozen=True)
class CaseScore:
    """The verdicts of one valid case, next to the case and the answer they came from."""

    case: GoldenCase
    result: CaseResult
    outcome: CategoryOutcome
    format: FormatResult | None  # None when there is no answer

    @property
    def category_pass(self) -> bool:
        return self.outcome in (CategoryOutcome.EXACT, CategoryOutcome.ACCEPTABLE)

    @property
    def format_pass(self) -> bool:
        return self.format is not None and self.format.passed

    @property
    def summary_words(self) -> int | None:
        summary = self.result.summary
        return len(summary.split()) if summary is not None else None


@dataclass(frozen=True)
class RunScores:
    """A run scored: one score per valid case, in golden order, and the excluded case ids."""

    record: RunRecord
    scores: tuple[CaseScore, ...]
    excluded: tuple[str, ...]  # infrastructure errors (decision 1.6)


def category_outcome(case: GoldenCase, predicted: Category | None) -> CategoryOutcome:
    if predicted is None:
        return CategoryOutcome.NO_ANSWER
    if predicted == case.expected_category:
        return CategoryOutcome.EXACT
    if predicted in case.acceptable_categories:
        return CategoryOutcome.ACCEPTABLE
    return CategoryOutcome.MISS


def score_case(case: GoldenCase, result: CaseResult) -> CaseScore:
    """Score one answer; an infrastructure error has no score and is refused here."""
    if result.case_id != case.id:
        raise ValueError(f"result {result.case_id} does not belong to case {case.id}")
    if result.status == LLMStatus.ERROR:
        raise ValueError(f"case {case.id} ended in an infrastructure error and is not scored")
    if result.status in NO_ANSWER_STATUSES or result.summary is None:
        return CaseScore(case, result, CategoryOutcome.NO_ANSWER, None)
    out_of_scope = EdgeType.OUT_OF_SCOPE in case.edge_types
    return CaseScore(
        case=case,
        result=result,
        outcome=category_outcome(case, result.category),
        format=check_format(result.summary, out_of_scope=out_of_scope),
    )


def score_run(edition: GoldenEdition, record: RunRecord) -> RunScores:
    """Score every case of a run against the edition it used."""
    if record.info.golden.edition != edition.edition:
        raise ValueError(
            f"the run used edition {record.info.golden.edition}, not edition {edition.edition}"
        )
    cases = {case.id: case for case in edition.cases}
    if set(cases) != {result.case_id for result in record.cases}:
        raise ValueError("the run and the golden edition do not have the same cases")
    scores = []
    excluded = []
    for result in record.cases:
        if result.status == LLMStatus.ERROR:
            excluded.append(result.case_id)
        else:
            scores.append(score_case(cases[result.case_id], result))
    return RunScores(record=record, scores=tuple(scores), excluded=tuple(excluded))
