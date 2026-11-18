"""Paired comparison on the 140-case matrix: counts, rates, exclusions and the diff lists."""

import pytest

from regression_detector.compare.paired import ComparisonError, Signal, compare_runs
from regression_detector.feature.models import Category
from regression_detector.ports.llm import LLMStatus, Usage
from tests.factories import case_data, full_matrix_cases, make_edition, scored_run

CASES = full_matrix_cases()
CASES[0] = CASES[0] | {"acceptable_categories": ["cancellation"]}  # delivery-001
EDITION = make_edition(CASES)

MISS = {"category": Category.GENERAL}  # every case below expects another category
ERROR = {"status": LLMStatus.ERROR, "category": None, "summary": None, "usage": Usage()}
BAD_FORMAT = {"summary": "O cliente pede ajuda. E quer o rastreio."}

BASELINE = scored_run(EDITION, {"delivery-002": MISS, "delivery-003": MISS, "account-001": ERROR})
CANDIDATE = scored_run(
    EDITION,
    {
        "delivery-001": {"category": Category.CANCELLATION},  # exact -> acceptable
        "delivery-003": MISS,  # failed on both sides
        "payment-001": MISS,
        "payment-002": MISS,
        "technical-019": MISS,  # adversarial
        "cancellation-001": BAD_FORMAT,
        "general-001": {"summary": "Cliente pergunta outra coisa sobre o pedido."},
        "account-002": ERROR,
    },
)
COMPARISON = compare_runs(BASELINE, CANDIDATE)


def test_errors_on_either_side_are_excluded_from_both():
    assert COMPARISON.excluded == ("account-001", "account-002")
    assert len(COMPARISON.pairs) == 138
    assert all(signal.n == 138 for signal in COMPARISON.signals)


def test_category_regressions_and_improvements():
    category = COMPARISON.signal(Signal.CATEGORY)
    assert category.regressions == ("payment-001", "payment-002", "technical-019")
    assert category.improvements == ("delivery-002",)
    assert category.net_drop == 2
    assert (category.baseline_passed, category.candidate_passed) == (136, 134)
    assert category.delta_pp == pytest.approx(-2 / 138 * 100)


def test_format_and_strict_signals():
    assert COMPARISON.signal(Signal.FORMAT).regressions == ("cancellation-001",)
    strict = COMPARISON.signal(Signal.STRICT)
    assert strict.regressions == ("delivery-001", "payment-001", "payment-002", "technical-019")
    assert strict.net_drop == 3


def test_the_diff_lists():
    assert COMPARISON.invariant_violations == ("technical-019",)
    assert COMPARISON.exact_to_acceptable == ("delivery-001",)
    # delivery-001 changed label and general-001 changed summary, with the same verdicts.
    assert COMPARISON.changed_without_verdict_change == 2


def test_groups_carry_their_size_and_highlight_net_drops_of_two():
    groups = {(g.dimension, g.value): g for g in COMPARISON.groups}
    payment = groups[("category", "payment")]
    assert (payment.n, payment.regressions, payment.improvements) == (20, 2, 0)
    assert payment.highlighted
    delivery = groups[("category", "delivery")]
    assert (delivery.net_drop, delivery.highlighted) == (-1, False)
    assert groups[("category", "account")].n == 18
    assert groups[("case_type", "adversarial")].regressions == 1
    assert not groups[("case_type", "adversarial")].highlighted


def test_served_models_of_each_side():
    candidate = scored_run(
        EDITION, {case.id: {"served_model": "gpt-6-luna-2026-11-15"} for case in EDITION.cases}
    )
    comparison = compare_runs(BASELINE, candidate)
    assert comparison.baseline_served_models == ("gpt-6-luna-2026-10-01",)
    assert comparison.candidate_served_models == ("gpt-6-luna-2026-11-15",)


def test_runs_of_different_golden_files_are_refused():
    other = scored_run(EDITION, golden_sha256="1" * 64)
    with pytest.raises(ComparisonError, match="different golden files"):
        compare_runs(BASELINE, other)


def test_runs_with_different_cases_are_refused():
    small = make_edition([case_data(id="delivery-001")])
    with pytest.raises(ComparisonError, match="same cases"):
        compare_runs(BASELINE, scored_run(small))


def test_a_comparison_needs_one_valid_pair():
    small = make_edition([case_data(id="delivery-001")])
    with pytest.raises(ComparisonError, match="no case is valid"):
        compare_runs(scored_run(small, {"delivery-001": ERROR}), scored_run(small))
