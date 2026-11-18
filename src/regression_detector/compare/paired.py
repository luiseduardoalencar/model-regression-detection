"""Paired comparison of two scored runs on the same golden edition (decisions 3.5 and 3.6).

Cases are paired by `id`. A case with an infrastructure error on either side is left out
of both (decision 1.6). Rates are computed on the paired cases, so the baseline and the
candidate are always measured on exactly the same cases (decided 2026-11-18).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from regression_detector.eval.scoring import CaseScore, CategoryOutcome, RunScores
from regression_detector.feature.models import Category
from regression_detector.golden.schema import CaseType, Difficulty, EdgeType, GoldenCase, Language

# A group (category or slice) whose net drop reaches this is highlighted; it never
# changes the verdict (decision 3.6).
HIGHLIGHT_NET_DROP = 2
NO_EDGE_TYPE = "none"


class ComparisonError(ValueError):
    """The two runs cannot be compared (different golden editions or cases)."""


class Signal(StrEnum):
    """A per-case pass/fail signal compared between the two sides."""

    CATEGORY = "category"  # category_pass: exact or acceptable (may block)
    FORMAT = "format"  # format_pass: the four code checks (may block)
    STRICT = "strict"  # exact label only (advisory)


_PASSES: dict[Signal, Callable[[CaseScore], bool]] = {
    Signal.CATEGORY: lambda score: score.category_pass,
    Signal.FORMAT: lambda score: score.format_pass,
    Signal.STRICT: lambda score: score.outcome == CategoryOutcome.EXACT,
}


@dataclass(frozen=True)
class CasePair:
    """One golden case as scored in the baseline and in the candidate."""

    case: GoldenCase
    baseline: CaseScore
    candidate: CaseScore

    def passed(self, signal: Signal) -> tuple[bool, bool]:
        """Whether the case passed the signal in the baseline and in the candidate."""
        check = _PASSES[signal]
        return check(self.baseline), check(self.candidate)

    @property
    def output_changed(self) -> bool:
        before, after = self.baseline.result, self.candidate.result
        return (before.category, before.summary) != (after.category, after.summary)


@dataclass(frozen=True)
class SignalDelta:
    """Baseline vs candidate on one signal, over the paired cases."""

    signal: Signal
    n: int
    baseline_passed: int
    candidate_passed: int
    regressions: tuple[str, ...]  # case ids, pass -> fail
    improvements: tuple[str, ...]  # case ids, fail -> pass

    @property
    def net_drop(self) -> int:
        return len(self.regressions) - len(self.improvements)

    @property
    def baseline_rate(self) -> float:
        return self.baseline_passed / self.n

    @property
    def candidate_rate(self) -> float:
        return self.candidate_passed / self.n

    @property
    def delta_pp(self) -> float:
        """Candidate minus baseline, in percentage points."""
        return (self.candidate_passed - self.baseline_passed) / self.n * 100


@dataclass(frozen=True)
class GroupDelta:
    """Category-pass changes within one category or slice, with its size."""

    dimension: str
    value: str
    n: int
    regressions: int
    improvements: int

    @property
    def net_drop(self) -> int:
        return self.regressions - self.improvements

    @property
    def highlighted(self) -> bool:
        return self.net_drop >= HIGHLIGHT_NET_DROP


@dataclass(frozen=True)
class Comparison:
    """Everything the gate and the report need from two scored runs."""

    baseline: RunScores
    candidate: RunScores
    pairs: tuple[CasePair, ...]  # golden order
    excluded: tuple[str, ...]  # infrastructure error on either side
    signals: tuple[SignalDelta, ...]
    invariant_violations: tuple[str, ...]  # adversarial cases, category pass -> fail
    exact_to_acceptable: tuple[str, ...]
    changed_without_verdict_change: int
    groups: tuple[GroupDelta, ...]
    baseline_served_models: tuple[str, ...]
    candidate_served_models: tuple[str, ...]

    def signal(self, signal: Signal) -> SignalDelta:
        return next(delta for delta in self.signals if delta.signal == signal)


def compare_runs(baseline: RunScores, candidate: RunScores) -> Comparison:
    """Pair the two runs by case id and measure every change."""
    _check_comparable(baseline, candidate)
    excluded = set(baseline.excluded) | set(candidate.excluded)
    after = {score.case.id: score for score in candidate.scores}
    pairs = tuple(
        CasePair(case=score.case, baseline=score, candidate=after[score.case.id])
        for score in baseline.scores
        if score.case.id not in excluded
    )
    if not pairs:
        raise ComparisonError("no case is valid on both sides")
    return Comparison(
        baseline=baseline,
        candidate=candidate,
        pairs=pairs,
        excluded=tuple(
            result.case_id for result in baseline.record.cases if result.case_id in excluded
        ),
        signals=tuple(_signal_delta(signal, pairs) for signal in Signal),
        invariant_violations=tuple(
            pair.case.id
            for pair in pairs
            if pair.case.case_type == CaseType.ADVERSARIAL
            and pair.passed(Signal.CATEGORY) == (True, False)
        ),
        exact_to_acceptable=tuple(
            pair.case.id
            for pair in pairs
            if pair.baseline.outcome == CategoryOutcome.EXACT
            and pair.candidate.outcome == CategoryOutcome.ACCEPTABLE
        ),
        changed_without_verdict_change=sum(
            pair.output_changed
            and pair.passed(Signal.CATEGORY)[0] == pair.passed(Signal.CATEGORY)[1]
            and pair.passed(Signal.FORMAT)[0] == pair.passed(Signal.FORMAT)[1]
            for pair in pairs
        ),
        groups=_groups(pairs),
        baseline_served_models=_served_models(pair.baseline for pair in pairs),
        candidate_served_models=_served_models(pair.candidate for pair in pairs),
    )


def _check_comparable(baseline: RunScores, candidate: RunScores) -> None:
    golden_before, golden_after = baseline.record.info.golden, candidate.record.info.golden
    if (golden_before.edition, golden_before.sha256) != (golden_after.edition, golden_after.sha256):
        raise ComparisonError(
            f"the runs used different golden files (edition {golden_before.edition} "
            f"{golden_before.sha256[:12]} vs edition {golden_after.edition} "
            f"{golden_after.sha256[:12]})"
        )
    ids_before = {result.case_id for result in baseline.record.cases}
    ids_after = {result.case_id for result in candidate.record.cases}
    if ids_before != ids_after:
        raise ComparisonError("the runs do not have the same cases")


def _signal_delta(signal: Signal, pairs: tuple[CasePair, ...]) -> SignalDelta:
    outcomes = [(pair.case.id, *pair.passed(signal)) for pair in pairs]
    return SignalDelta(
        signal=signal,
        n=len(pairs),
        baseline_passed=sum(before for _, before, _ in outcomes),
        candidate_passed=sum(after for _, _, after in outcomes),
        regressions=tuple(case_id for case_id, before, after in outcomes if before and not after),
        improvements=tuple(case_id for case_id, before, after in outcomes if after and not before),
    )


def _group_keys(case: GoldenCase) -> list[tuple[str, str]]:
    edge_types = [edge.value for edge in case.edge_types] or [NO_EDGE_TYPE]
    return [
        ("category", case.expected_category.value),
        ("case_type", case.case_type.value),
        ("difficulty", case.expected_difficulty.value),
        ("language", case.language.value),
        *(("edge_type", edge) for edge in edge_types),
    ]


_GROUP_ORDER = [
    *(("category", c.value) for c in Category),
    *(("case_type", t.value) for t in CaseType),
    *(("difficulty", d.value) for d in Difficulty),
    *(("language", lang.value) for lang in Language),
    *(("edge_type", e.value) for e in EdgeType),
    ("edge_type", NO_EDGE_TYPE),
]


def _groups(pairs: tuple[CasePair, ...]) -> tuple[GroupDelta, ...]:
    groups = []
    for dimension, value in _GROUP_ORDER:
        members = [pair for pair in pairs if (dimension, value) in _group_keys(pair.case)]
        if not members:
            continue
        flips = [pair.passed(Signal.CATEGORY) for pair in members]
        groups.append(
            GroupDelta(
                dimension=dimension,
                value=value,
                n=len(members),
                regressions=sum(before and not after for before, after in flips),
                improvements=sum(after and not before for before, after in flips),
            )
        )
    return tuple(groups)


def _served_models(scores: Iterable[CaseScore]) -> tuple[str, ...]:
    return tuple(sorted({s.result.served_model for s in scores if s.result.served_model}))
