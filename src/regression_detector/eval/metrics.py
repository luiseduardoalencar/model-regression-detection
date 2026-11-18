"""Run metrics (decision 3.1): accuracies, per-category report, confusion matrix, slices, numbers.

Denominators are the valid cases (infrastructure errors excluded, decision 1.6); a case
without an answer counts as wrong.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from statistics import median

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

from regression_detector.eval.scoring import CaseScore, CategoryOutcome, RunScores
from regression_detector.feature.models import Category
from regression_detector.golden.schema import CaseType, Difficulty, EdgeType, Language

NO_ANSWER = "no_answer"
CATEGORIES = tuple(category.value for category in Category)
NO_EDGE_TYPE = "none"


@dataclass(frozen=True)
class CategoryMetrics:
    """Strict-label precision, recall and F1 of one category, with its support (cases)."""

    category: Category
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class SliceMetrics:
    """Accuracies of one slice of the golden set, always with its size."""

    dimension: str
    value: str
    n: int
    strict_accuracy: float
    acceptable_accuracy: float


@dataclass(frozen=True)
class LatencyStats:
    """Latency in milliseconds: median, 95th percentile and maximum."""

    p50: float
    p95: float
    max: float


@dataclass(frozen=True)
class TokenStats:
    """Total and mean tokens per valid case."""

    input_total: int
    cached_input_total: int
    output_total: int
    reasoning_total: int
    input_mean: float
    output_mean: float


@dataclass(frozen=True)
class RunMetrics:
    """Every number of a scored run (decision 3.1 plus the advisory numbers of 3.4)."""

    valid_cases: int
    excluded_cases: int
    strict_accuracy: float
    acceptable_accuracy: float
    format_pass_rate: float
    per_category: tuple[CategoryMetrics, ...]
    macro_f1: float
    confusion_columns: tuple[str, ...]  # the 7 categories in enum order, then "no_answer"
    confusion: tuple[tuple[int, ...], ...]  # rows: expected category, enum order
    slices: tuple[SliceMetrics, ...]
    latency_ms: LatencyStats
    tokens: TokenStats
    exam_cost_usd: float
    spent_usd: float
    summary_words_median: float | None
    summary_words_max: int | None


def _rate(passed: int, total: int) -> float:
    return passed / total if total else 0.0


def _accuracies(scores: Iterable[CaseScore]) -> tuple[int, float, float]:
    scores = list(scores)
    strict = sum(score.outcome == CategoryOutcome.EXACT for score in scores)
    acceptable = sum(score.category_pass for score in scores)
    return len(scores), _rate(strict, len(scores)), _rate(acceptable, len(scores))


def _predicted_label(score: CaseScore) -> str:
    category = score.result.category
    return category.value if score.outcome != CategoryOutcome.NO_ANSWER and category else NO_ANSWER


def _slices(scores: tuple[CaseScore, ...]) -> tuple[SliceMetrics, ...]:
    dimensions: list[tuple[str, list[str], Callable[[CaseScore], Iterable[str]]]] = [
        ("case_type", [v.value for v in CaseType], lambda s: [s.case.case_type.value]),
        ("difficulty", [v.value for v in Difficulty], lambda s: [s.case.expected_difficulty.value]),
        ("language", [v.value for v in Language], lambda s: [s.case.language.value]),
        (
            "edge_type",
            [v.value for v in EdgeType] + [NO_EDGE_TYPE],
            lambda s: [e.value for e in s.case.edge_types] or [NO_EDGE_TYPE],
        ),
    ]
    slices = []
    for dimension, values, keys_of in dimensions:
        for value in values:
            members = [score for score in scores if value in keys_of(score)]
            if members:
                n, strict, acceptable = _accuracies(members)
                slices.append(SliceMetrics(dimension, value, n, strict, acceptable))
    return tuple(slices)


def compute_metrics(run: RunScores) -> RunMetrics:
    """All the numbers of one scored run."""
    scores = run.scores
    if not scores:
        raise ValueError("a run without valid cases has no metrics")
    y_true = [score.case.expected_category.value for score in scores]
    y_pred = [_predicted_label(score) for score in scores]
    report = classification_report(
        y_true, y_pred, labels=list(CATEGORIES), output_dict=True, zero_division=0
    )
    columns = (*CATEGORIES, NO_ANSWER)
    matrix = confusion_matrix(y_true, y_pred, labels=list(columns))[: len(CATEGORIES)]
    n, strict, acceptable = _accuracies(scores)
    latencies = [score.result.latency_ms for score in scores]
    p50, p95 = np.percentile(latencies, [50, 95])
    usages = [score.result.usage for score in scores]
    words = [score.summary_words for score in scores if score.summary_words is not None]
    return RunMetrics(
        valid_cases=n,
        excluded_cases=len(run.excluded),
        strict_accuracy=strict,
        acceptable_accuracy=acceptable,
        format_pass_rate=_rate(sum(score.format_pass for score in scores), n),
        per_category=tuple(
            CategoryMetrics(
                category=Category(label),
                precision=float(report[label]["precision"]),
                recall=float(report[label]["recall"]),
                f1=float(report[label]["f1-score"]),
                support=int(report[label]["support"]),
            )
            for label in CATEGORIES
        ),
        macro_f1=float(report["macro avg"]["f1-score"]),
        confusion_columns=columns,
        confusion=tuple(tuple(int(cell) for cell in row) for row in matrix),
        slices=_slices(scores),
        latency_ms=LatencyStats(p50=float(p50), p95=float(p95), max=max(latencies)),
        tokens=TokenStats(
            input_total=sum(u.input_tokens for u in usages),
            cached_input_total=sum(u.cached_input_tokens for u in usages),
            output_total=sum(u.output_tokens for u in usages),
            reasoning_total=sum(u.reasoning_tokens for u in usages),
            input_mean=sum(u.input_tokens for u in usages) / n,
            output_mean=sum(u.output_tokens for u in usages) / n,
        ),
        exam_cost_usd=run.record.exam_cost_usd,
        spent_usd=run.record.spent_usd,
        summary_words_median=float(median(words)) if words else None,
        summary_words_max=max(words) if words else None,
    )
