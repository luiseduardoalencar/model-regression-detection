"""Per-case scoring: every path of a case, and a run scored against its edition."""

import pytest

from regression_detector.eval.scoring import CategoryOutcome, score_case, score_run
from regression_detector.feature.models import Category
from regression_detector.golden.schema import GoldenCase
from regression_detector.ports.llm import LLMStatus
from tests.factories import case_data, case_result, make_edition, run_record

CASE = GoldenCase.model_validate(case_data(acceptable_categories=["cancellation"]))


@pytest.mark.parametrize(
    ("predicted", "outcome", "category_pass"),
    [
        (Category.DELIVERY, CategoryOutcome.EXACT, True),
        (Category.CANCELLATION, CategoryOutcome.ACCEPTABLE, True),
        (Category.PAYMENT, CategoryOutcome.MISS, False),
    ],
)
def test_category_outcomes(predicted, outcome, category_pass):
    score = score_case(CASE, case_result(category=predicted))
    assert score.outcome == outcome
    assert score.category_pass is category_pass
    assert score.format_pass is True
    assert score.summary_words == 5


@pytest.mark.parametrize(
    "status", [LLMStatus.REFUSAL, LLMStatus.INCOMPLETE, LLMStatus.INVALID_OUTPUT]
)
def test_no_answer_fails_category_and_format(status):
    score = score_case(CASE, case_result(status=status, category=None, summary=None))
    assert score.outcome == CategoryOutcome.NO_ANSWER
    assert score.category_pass is False
    assert score.format is None
    assert score.format_pass is False
    assert score.summary_words is None


def test_format_failures_are_kept_with_their_reason():
    score = score_case(CASE, case_result(summary="O cliente quer o pedido. E o rastreio."))
    assert score.category_pass is True
    assert score.format_pass is False
    assert [check.detail for check in score.format.failures] == [
        "2 sentences",
        "starts with 'O cliente'",
    ]


def test_out_of_scope_cases_may_start_without_cliente():
    case = GoldenCase.model_validate(
        case_data(
            id="general-008",
            expected_category="general",
            case_type="adversarial",
            expected_difficulty="hard",
            edge_types=["out_of_scope"],
        )
    )
    result = case_result("general-008", category=Category.GENERAL, summary="Email de propaganda.")
    assert score_case(case, result).format_pass is True


def test_infrastructure_errors_are_not_scored():
    with pytest.raises(ValueError, match="infrastructure error"):
        score_case(CASE, case_result(status=LLMStatus.ERROR, category=None, summary=None))


def test_a_result_of_another_case_is_refused():
    with pytest.raises(ValueError, match="does not belong"):
        score_case(CASE, case_result("payment-001"))


def test_score_run_excludes_infrastructure_errors_and_keeps_order():
    edition = make_edition(
        [case_data(id="delivery-001"), case_data(id="delivery-002"), case_data(id="delivery-003")]
    )
    record = run_record(
        [
            case_result("delivery-001"),
            case_result("delivery-002", status=LLMStatus.ERROR, category=None, summary=None),
            case_result("delivery-003"),
        ]
    )
    run = score_run(edition, record)
    assert [score.case.id for score in run.scores] == ["delivery-001", "delivery-003"]
    assert run.excluded == ("delivery-002",)
    assert run.record is record


def test_score_run_refuses_a_run_of_other_cases_or_edition():
    edition = make_edition([case_data(id="delivery-001")])
    with pytest.raises(ValueError, match="same cases"):
        score_run(edition, run_record([case_result("delivery-002")]))
    with pytest.raises(ValueError, match="edition 2"):
        score_run(edition, run_record([case_result("delivery-001")], edition=2))
