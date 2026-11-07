"""Each validation rule produces its flag, and a complete edition produces none."""

from collections import Counter

import pytest

from regression_detector.golden.schema import CaseType, Language
from regression_detector.golden.validation import (
    FlagKind,
    Severity,
    check_duplicates,
    check_edge_types,
    check_matrix,
    coverage_summary,
    validate,
)
from tests.factories import case_data, full_matrix_cases, make_edition


def test_complete_edition_has_no_flags():
    assert validate(make_edition(full_matrix_cases())) == []


def test_missing_case_is_a_matrix_gap():
    cases = [case for case in full_matrix_cases() if case["id"] != "delivery-001"]
    flags = check_matrix(make_edition(cases))
    assert [flag.message for flag in flags] == ["delivery has 13 typical cases, expected 14"]


def test_too_few_hard_cases_is_a_matrix_gap():
    cases = full_matrix_cases()
    hard = [case for case in cases if case["expected_difficulty"] == "hard"]
    for case in hard[: len(hard) - 34]:
        case["expected_difficulty"] = "medium"
    flags = check_matrix(make_edition(cases))
    assert [flag.message for flag in flags] == ["34 hard cases, expected at least 35"]


def test_rare_edge_type_is_a_matrix_gap():
    cases = full_matrix_cases()
    for case in cases:
        if case["edge_types"] == ["sarcasm"]:
            case["edge_types"] = ["typos"]
    flags = check_matrix(make_edition(cases))
    assert [flag.message for flag in flags] == [
        "edge type sarcasm appears in 0 edge cases, expected at least 2"
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"case_type": "adversarial"}, id="adversarial without type"),
        pytest.param(
            {"case_type": "adversarial", "edge_types": ["out_of_scope"]},
            id="out_of_scope outside general",
        ),
        pytest.param(
            {
                "id": "general-001",
                "expected_category": "general",
                "case_type": "adversarial",
                "edge_types": ["prompt_injection"],
            },
            id="general adversarial must be out_of_scope",
        ),
        pytest.param({"case_type": "edge"}, id="edge without type"),
        pytest.param({"edge_types": ["label_forcing"]}, id="adversarial type on typical case"),
    ],
)
def test_edge_type_rules(overrides):
    flags = check_edge_types(make_edition([case_data(**overrides)]))
    assert [flag.kind for flag in flags] == [FlagKind.EDGE_TYPE_RULE]


def test_label_conflict_is_listed_first():
    email = "O pedido 4521 chegou com a tela quebrada e quero devolver"
    edition = make_edition(
        [
            case_data(id="return_refund-001", expected_category="return_refund", input_email=email),
            case_data(id="delivery-001", input_email=email.upper()),
        ]
    )
    flags = validate(edition)
    assert flags[0].kind == FlagKind.LABEL_CONFLICT
    assert FlagKind.EXACT_DUPLICATE in [flag.kind for flag in flags]


def test_similar_pair_with_same_label_only_warns():
    edition = make_edition(
        [
            case_data(
                id="delivery-001",
                input_email="Meu pedido 4521 não chegou e o rastreio está parado há uma semana",
            ),
            case_data(
                id="delivery-002",
                input_email="Meu pedido 7788 não chegou e o rastreio parou faz uma semana",
            ),
        ]
    )
    flags = check_duplicates(edition)
    assert [(flag.kind, flag.severity) for flag in flags] == [
        (FlagKind.SIMILAR_PAIR, Severity.WARN)
    ]


def test_coverage_summary_counts_language_per_case_type():
    edition = make_edition(
        [
            case_data(id="delivery-001", language="en"),
            case_data(id="delivery-002"),
            case_data(id="delivery-003", case_type="edge", edge_types=["typos"]),
        ]
    )
    summaries = {summary.case_type: summary for summary in coverage_summary(edition)}
    assert summaries[CaseType.TYPICAL].languages == Counter({Language.EN: 1, Language.PT: 1})
    assert summaries[CaseType.EDGE].total == 1
    assert CaseType.ADVERSARIAL not in summaries
