"""The gate verdict of a comparison (decisions 1.6, 3.4 and 3.5) and its exit code.

Every rule that fires is listed; the strongest decides the verdict, in this order:
inconclusive, blocked, warning, passed (decided 2026-11-18).
"""

from dataclasses import dataclass
from enum import StrEnum

from regression_detector.compare.gate_config import AdversarialMode, GateConfig
from regression_detector.compare.paired import Comparison, Signal
from regression_detector.eval.scoring import RunScores
from regression_detector.eval.validity import RunValidity, assess_validity


class Verdict(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"


# GitHub Actions treats 0 as success and anything else as failure; 1 and 2 keep
# "got worse" apart from "could not be measured" (decision 3.4).
EXIT_CODES = {
    Verdict.PASSED: 0,
    Verdict.WARNING: 0,
    Verdict.BLOCKED: 1,
    Verdict.INCONCLUSIVE: 2,
}


class Severity(StrEnum):
    """What a fired rule does to the verdict."""

    INCONCLUSIVE = "inconclusive"
    BLOCK = "block"
    WARN = "warn"


class Rule(StrEnum):
    INFRA_ERRORS = "infra_errors"
    NET_DROP = "net_drop"
    ADVERSARIAL_INVARIANT = "adversarial_invariant"
    ABSOLUTE_FLOOR = "absolute_floor"
    SERVED_MODEL = "served_model"


@dataclass(frozen=True)
class FiredRule:
    """One rule that fired, with the numbers behind it."""

    rule: Rule
    severity: Severity
    detail: str


@dataclass(frozen=True)
class GateResult:
    """The verdict, every rule that fired and the comparison it came from."""

    verdict: Verdict
    rules: tuple[FiredRule, ...]
    comparison: Comparison

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]


def decide(comparison: Comparison, config: GateConfig) -> GateResult:
    """Apply every gate rule to the comparison and return the verdict."""
    edition = comparison.candidate.record.info.golden.edition
    if edition != config.golden_edition:
        raise ValueError(
            f"the runs used golden edition {edition}; config/gate.yaml expects edition "
            f"{config.golden_edition}"
        )
    rules = [
        *_infra_errors(comparison, config),
        *_net_drops(comparison, config),
        *_adversarial(comparison, config),
        *_floors(comparison.candidate, config),
        *_served_model(comparison),
    ]
    return GateResult(verdict=_verdict(rules), rules=tuple(rules), comparison=comparison)


def _verdict(rules: list[FiredRule]) -> Verdict:
    severities = {rule.severity for rule in rules}
    if Severity.INCONCLUSIVE in severities:
        return Verdict.INCONCLUSIVE
    if Severity.BLOCK in severities:
        return Verdict.BLOCKED
    if Severity.WARN in severities:
        return Verdict.WARNING
    return Verdict.PASSED


def _infra_errors(comparison: Comparison, config: GateConfig) -> list[FiredRule]:
    fired = []
    limit = config.infra_error_limit_percent
    for side, run in (("baseline", comparison.baseline), ("candidate", comparison.candidate)):
        errors, total = run.record.infra_errors, len(run.record.cases)
        if assess_validity(errors, total, limit).validity == RunValidity.INCONCLUSIVE:
            fired.append(
                FiredRule(
                    Rule.INFRA_ERRORS,
                    Severity.INCONCLUSIVE,
                    f"{side}: {errors} of {total} cases ({errors / total:.1%}) ended in an "
                    f"infrastructure error; the limit is {limit} %; re-run",
                )
            )
    return fired


def _net_drops(comparison: Comparison, config: GateConfig) -> list[FiredRule]:
    thresholds = config.net_drop
    fired = []
    for signal in (Signal.CATEGORY, Signal.FORMAT, Signal.STRICT):
        delta = comparison.signal(signal)
        if delta.net_drop >= thresholds.block and signal != Signal.STRICT:
            severity = Severity.BLOCK
        elif delta.net_drop >= thresholds.warn:
            severity = Severity.WARN
        else:
            continue
        fired.append(
            FiredRule(
                Rule.NET_DROP,
                severity,
                f"{signal}: net drop of {delta.net_drop} cases ({len(delta.regressions)} "
                f"regressions, {len(delta.improvements)} improvements; "
                f"{delta.delta_pp:+.1f} pp)",
            )
        )
    return fired


def _adversarial(comparison: Comparison, config: GateConfig) -> list[FiredRule]:
    if not comparison.invariant_violations:
        return []
    severity = (
        Severity.BLOCK if config.adversarial_invariant == AdversarialMode.BLOCK else Severity.WARN
    )
    cases = ", ".join(comparison.invariant_violations)
    return [
        FiredRule(
            Rule.ADVERSARIAL_INVARIANT,
            severity,
            f"adversarial cases went from pass to fail: {cases}",
        )
    ]


def _floors(candidate: RunScores, config: GateConfig) -> list[FiredRule]:
    # The floor is absolute: the candidate on its own valid cases, not compared with anything.
    scores = candidate.scores
    rates = {
        "acceptable_accuracy": sum(score.category_pass for score in scores) / len(scores),
        "format_pass_rate": sum(score.format_pass for score in scores) / len(scores),
    }
    floors = config.absolute_floor
    fired = []
    for name, floor in (
        ("acceptable_accuracy", floors.acceptable_accuracy),
        ("format_pass_rate", floors.format_pass_rate),
    ):
        if floor is not None and rates[name] < floor:
            fired.append(
                FiredRule(
                    Rule.ABSOLUTE_FLOOR,
                    Severity.BLOCK,
                    f"candidate {name} {rates[name]:.1%} is below the floor of {floor:.1%}",
                )
            )
    return fired


def _served_model(comparison: Comparison) -> list[FiredRule]:
    before, after = comparison.baseline_served_models, comparison.candidate_served_models
    if before == after:
        return []
    return [
        FiredRule(
            Rule.SERVED_MODEL,
            Severity.WARN,
            f"served model differs: baseline {', '.join(before) or 'none'}, candidate "
            f"{', '.join(after) or 'none'}; part of the difference may come from the model",
        )
    ]
