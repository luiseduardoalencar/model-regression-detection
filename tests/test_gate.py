"""Gate verdicts on hand-made runs: the plan's scenarios, the boundaries and the precedence."""

from pathlib import Path

import pytest

from regression_detector.compare.gate import EXIT_CODES, Rule, Severity, Verdict, decide
from regression_detector.compare.gate_config import AbsoluteFloor, AdversarialMode, load_gate_config
from regression_detector.compare.paired import compare_runs
from regression_detector.feature.models import Category
from regression_detector.ports.llm import LLMStatus, Usage
from tests.factories import full_matrix_cases, make_edition, scored_run

CONFIG = load_gate_config(Path(__file__).parents[1] / "config" / "gate.yaml")
EDITION = make_edition(full_matrix_cases())
TYPICAL = [case.id for case in EDITION.cases if case.case_type == "typical"]
ADVERSARIAL = [case.id for case in EDITION.cases if case.case_type == "adversarial"]

MISS = {"category": Category.GENERAL}
ERROR = {"status": LLMStatus.ERROR, "category": None, "summary": None, "usage": Usage()}
BAD_FORMAT = {"summary": "O cliente pede ajuda. E quer o rastreio."}
CLEAN = scored_run(EDITION)


def failing(ids: list[str], change: dict | None = None) -> dict[str, dict]:
    """`change` (a category miss by default) applied to the given typical cases."""
    for case_id in ids:
        assert not case_id.startswith("general")  # MISS predicts general
    return {case_id: change or MISS for case_id in ids}


def verdict_of(baseline, candidate, config=CONFIG):
    return decide(compare_runs(baseline, candidate), config)


def rules_of(result) -> set[tuple[Rule, Severity]]:
    return {(rule.rule, rule.severity) for rule in result.rules}


def test_the_same_answers_pass():
    result = verdict_of(CLEAN, CLEAN)
    assert (result.verdict, result.exit_code, result.rules) == (Verdict.PASSED, 0, ())


@pytest.mark.parametrize(
    ("regressions", "verdict", "exit_code"),
    [
        (4, Verdict.PASSED, 0),  # plan scenario: 4 regressions pass
        (5, Verdict.WARNING, 0),
        (6, Verdict.WARNING, 0),
        (7, Verdict.BLOCKED, 1),  # plan scenario: 7 regressions block
    ],
)
def test_category_net_drop_thresholds(regressions, verdict, exit_code):
    result = verdict_of(CLEAN, scored_run(EDITION, failing(TYPICAL[:regressions])))
    assert (result.verdict, result.exit_code) == (verdict, exit_code)


def test_the_net_drop_counts_improvements():
    baseline = scored_run(EDITION, failing(TYPICAL[:1]))
    blocked = verdict_of(baseline, scored_run(EDITION, failing(TYPICAL[1:9])))  # 8 - 1 = 7
    warned = verdict_of(baseline, scored_run(EDITION, failing(TYPICAL[1:8])))  # 7 - 1 = 6
    assert (blocked.verdict, warned.verdict) == (Verdict.BLOCKED, Verdict.WARNING)


def test_a_format_drop_blocks_on_its_own():
    result = verdict_of(CLEAN, scored_run(EDITION, failing(TYPICAL[:7], BAD_FORMAT)))
    assert result.verdict == Verdict.BLOCKED
    assert result.comparison.signal("format").net_drop == 7
    assert result.comparison.signal("category").net_drop == 0


def test_one_adversarial_flip_blocks():  # plan scenario
    result = verdict_of(CLEAN, scored_run(EDITION, {ADVERSARIAL[0]: MISS}))
    assert result.verdict == Verdict.BLOCKED
    assert rules_of(result) == {(Rule.ADVERSARIAL_INVARIANT, Severity.BLOCK)}


def test_the_adversarial_invariant_can_be_demoted_to_a_warning():
    config = CONFIG.model_copy(update={"adversarial_invariant": AdversarialMode.WARN})
    result = verdict_of(CLEAN, scored_run(EDITION, {ADVERSARIAL[0]: MISS}), config)
    assert result.verdict == Verdict.WARNING


def test_too_many_infrastructure_errors_are_inconclusive():  # plan scenario: about 3 %
    result = verdict_of(CLEAN, scored_run(EDITION, failing(TYPICAL[:4], ERROR)))  # 2.9 %
    assert (result.verdict, result.exit_code) == (Verdict.INCONCLUSIVE, 2)
    assert "candidate: 4 of 140 cases" in result.rules[0].detail
    two = verdict_of(CLEAN, scored_run(EDITION, failing(TYPICAL[:2], ERROR)))  # 1.4 %
    assert two.verdict == Verdict.PASSED


def test_an_inconclusive_baseline_is_inconclusive_too():
    result = verdict_of(scored_run(EDITION, failing(TYPICAL[:3], ERROR)), CLEAN)
    assert result.verdict == Verdict.INCONCLUSIVE
    assert result.rules[0].detail.startswith("baseline: 3 of 140")


def test_inconclusive_wins_but_every_fired_rule_is_listed():
    candidate = scored_run(EDITION, failing(TYPICAL[:4], ERROR) | failing(TYPICAL[4:11]))
    result = verdict_of(CLEAN, candidate)
    assert result.verdict == Verdict.INCONCLUSIVE
    assert (Rule.NET_DROP, Severity.BLOCK) in rules_of(result)


def test_two_small_drops_crossing_the_floor_block():  # plan scenario
    floor = AbsoluteFloor(acceptable_accuracy=0.95)
    config = CONFIG.model_copy(update={"absolute_floor": floor})
    first_pr = scored_run(EDITION, failing(TYPICAL[:4]))  # 136/140 = 97.1 %, net drop 4
    second_pr = scored_run(EDITION, failing(TYPICAL[:8]))  # 132/140 = 94.3 %, net drop 4
    assert verdict_of(CLEAN, first_pr, config).verdict == Verdict.PASSED
    result = verdict_of(first_pr, second_pr, config)
    assert result.verdict == Verdict.BLOCKED
    assert rules_of(result) == {(Rule.ABSOLUTE_FLOOR, Severity.BLOCK)}
    assert "94.3% is below the floor of 95.0%" in result.rules[0].detail


def test_exactly_on_the_floor_passes():
    floor = AbsoluteFloor(acceptable_accuracy=133 / 140, format_pass_rate=133 / 140)
    config = CONFIG.model_copy(update={"absolute_floor": floor})
    seven = failing(TYPICAL[:7])
    result = verdict_of(scored_run(EDITION, seven), scored_run(EDITION, seven), config)
    assert result.verdict == Verdict.PASSED


def test_the_format_floor():
    config = CONFIG.model_copy(update={"absolute_floor": AbsoluteFloor(format_pass_rate=0.99)})
    bad = failing(TYPICAL[:2], BAD_FORMAT)  # 138/140 = 98.6 %
    result = verdict_of(scored_run(EDITION, bad), scored_run(EDITION, bad), config)
    assert result.verdict == Verdict.BLOCKED
    assert "format_pass_rate" in result.rules[0].detail


def test_a_strict_drop_only_warns():
    cases = full_matrix_cases()
    for case in cases[:8]:  # delivery-001..008 also accept cancellation
        case["acceptable_categories"] = ["cancellation"]
    edition = make_edition(cases)
    acceptable = {f"delivery-00{n}": {"category": Category.CANCELLATION} for n in range(1, 9)}
    result = verdict_of(scored_run(edition), scored_run(edition, acceptable))
    assert result.comparison.signal("strict").net_drop == 8
    assert result.verdict == Verdict.WARNING
    assert rules_of(result) == {(Rule.NET_DROP, Severity.WARN)}


def test_a_different_served_model_warns_without_softening_a_block():
    newer = {case.id: {"served_model": "gpt-6-luna-2026-11-15"} for case in EDITION.cases}
    alone = verdict_of(CLEAN, scored_run(EDITION, newer))
    assert alone.verdict == Verdict.WARNING
    assert "may come from the model" in alone.rules[0].detail
    with_drop = verdict_of(CLEAN, scored_run(EDITION, newer | failing(TYPICAL[:7])))
    assert with_drop.verdict == Verdict.BLOCKED
    assert (Rule.SERVED_MODEL, Severity.WARN) in rules_of(with_drop)


def test_runs_of_another_golden_edition_are_refused():
    config = CONFIG.model_copy(update={"golden_edition": 2})
    with pytest.raises(ValueError, match="config/gate.yaml expects edition 2"):
        verdict_of(CLEAN, CLEAN, config)


def test_exit_codes():
    assert EXIT_CODES == {
        Verdict.PASSED: 0,
        Verdict.WARNING: 0,
        Verdict.BLOCKED: 1,
        Verdict.INCONCLUSIVE: 2,
    }
