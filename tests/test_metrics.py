"""Run metrics on a small fabricated run whose numbers were computed by hand.

The run: 7 cases, one infrastructure error (excluded), so 6 valid cases.

| case             | expected     | predicted    | outcome    | format | slices            |
|------------------|--------------|--------------|------------|--------|-------------------|
| delivery-001     | delivery     | delivery     | exact      | pass   | typical, medium   |
| delivery-002     | delivery     | cancellation | acceptable | pass   | edge, temporal    |
| cancellation-001 | cancellation | delivery     | miss       | pass   | edge, negation    |
| payment-001      | payment      | payment      | exact      | fail   | typical, en       |
| payment-002      | payment      | (refusal)    | no answer  | fail   | typical, medium   |
| general-001      | general      | general      | exact      | pass   | out_of_scope      |
| account-001      | account      | (error)      | excluded   |        |                   |

delivery-002 accepts `cancellation`; the edge and out-of-scope cases are `hard`.
"""

import pytest

from regression_detector.eval.metrics import NO_ANSWER, compute_metrics
from regression_detector.eval.scoring import score_run
from regression_detector.feature.models import Category
from regression_detector.ports.llm import LLMStatus, Usage
from tests.factories import case_data, case_result, make_edition, run_record

EDGE = {"case_type": "edge", "expected_difficulty": "hard"}
EDITION = make_edition(
    [
        case_data(id="delivery-001"),
        case_data(
            id="delivery-002",
            acceptable_categories=["cancellation"],
            edge_types=["temporal"],
            **EDGE,
        ),
        case_data(
            id="cancellation-001", expected_category="cancellation", edge_types=["negation"], **EDGE
        ),
        case_data(id="payment-001", expected_category="payment", language="en"),
        case_data(id="payment-002", expected_category="payment"),
        case_data(
            id="general-001",
            expected_category="general",
            case_type="adversarial",
            expected_difficulty="hard",
            edge_types=["out_of_scope"],
        ),
        case_data(id="account-001", expected_category="account"),
    ]
)
RECORD = run_record(
    [
        case_result("delivery-001", summary="Cliente pergunta pelo pedido 123.", latency_ms=100.0),
        case_result(
            "delivery-002",
            category=Category.CANCELLATION,
            summary="Cliente quer cancelar o pedido 456 que atrasou.",
            latency_ms=200.0,
            from_local_cache=True,
        ),
        case_result(
            "cancellation-001",
            summary="Cliente diz que não quer cancelar e pergunta pela entrega.",
            latency_ms=300.0,
        ),
        case_result(
            "payment-001",
            category=Category.PAYMENT,
            summary="Customer asks for a refund of order 9.",
            latency_ms=400.0,
        ),
        case_result(
            "payment-002", status=LLMStatus.REFUSAL, category=None, summary=None, latency_ms=500.0
        ),
        case_result(
            "general-001",
            category=Category.GENERAL,
            summary="Email de propaganda de uma loja de fones.",
            latency_ms=600.0,
        ),
        case_result(
            "account-001",
            status=LLMStatus.ERROR,
            category=None,
            summary=None,
            usage=Usage(),
            cost_usd=0.0,
            latency_ms=60000.0,
        ),
    ]
)
METRICS = compute_metrics(score_run(EDITION, RECORD))


def test_headline_rates():
    assert (METRICS.valid_cases, METRICS.excluded_cases) == (6, 1)
    assert METRICS.strict_accuracy == pytest.approx(3 / 6)
    assert METRICS.acceptable_accuracy == pytest.approx(4 / 6)
    assert METRICS.format_pass_rate == pytest.approx(4 / 6)


def test_per_category_report_uses_strict_labels():
    report = {m.category: m for m in METRICS.per_category}
    assert list(report) == list(Category)
    delivery = report[Category.DELIVERY]  # predicted twice, right once; 2 expected, 1 found
    assert (delivery.precision, delivery.recall, delivery.f1, delivery.support) == (
        0.5,
        0.5,
        0.5,
        2,
    )
    cancellation = report[Category.CANCELLATION]  # the acceptable answer is wrong here
    assert (cancellation.precision, cancellation.recall, cancellation.support) == (0.0, 0.0, 1)
    payment = report[Category.PAYMENT]  # the refusal counts as a miss in recall
    assert (payment.precision, payment.recall, payment.support) == (1.0, 0.5, 2)
    assert payment.f1 == pytest.approx(2 / 3)
    assert report[Category.GENERAL].f1 == 1.0
    # Categories never expected nor predicted score 0 (zero_division=0), not a warning.
    assert report[Category.TECHNICAL].f1 == 0.0
    assert METRICS.macro_f1 == pytest.approx((0.5 + 0 + 2 / 3 + 1) / 7)


def test_confusion_matrix_has_a_no_answer_column():
    assert METRICS.confusion_columns == (*[c.value for c in Category], NO_ANSWER)
    rows = dict(zip([c.value for c in Category], METRICS.confusion, strict=True))
    assert rows["delivery"] == (1, 1, 0, 0, 0, 0, 0, 0)
    assert rows["cancellation"] == (1, 0, 0, 0, 0, 0, 0, 0)
    assert rows["payment"] == (0, 0, 0, 1, 0, 0, 0, 1)
    assert rows["general"] == (0, 0, 0, 0, 0, 0, 1, 0)
    assert rows["account"] == (0, 0, 0, 0, 0, 0, 0, 0)  # the errored case is excluded


def test_slices_always_carry_their_size():
    slices = {
        (s.dimension, s.value): (s.n, s.strict_accuracy, s.acceptable_accuracy)
        for s in METRICS.slices
    }
    assert slices[("case_type", "typical")] == (3, pytest.approx(2 / 3), pytest.approx(2 / 3))
    assert slices[("case_type", "edge")] == (2, 0.0, 0.5)
    assert slices[("case_type", "adversarial")] == (1, 1.0, 1.0)
    assert slices[("difficulty", "hard")] == (3, pytest.approx(1 / 3), pytest.approx(2 / 3))
    assert slices[("language", "en")] == (1, 1.0, 1.0)
    assert slices[("edge_type", "temporal")] == (1, 0.0, 1.0)
    assert slices[("edge_type", "out_of_scope")] == (1, 1.0, 1.0)
    assert slices[("edge_type", "none")][0] == 3
    assert ("case_type", "known_failure") not in slices  # empty slices are left out


def test_latency_tokens_cost_and_length():
    assert (METRICS.latency_ms.p50, METRICS.latency_ms.p95, METRICS.latency_ms.max) == (
        350.0,
        575.0,  # numpy's linear percentile: 500 + 0.75 x (600 - 500)
        600.0,
    )
    tokens = METRICS.tokens
    assert (tokens.input_total, tokens.cached_input_total, tokens.output_total) == (6000, 4800, 180)
    assert (tokens.input_mean, tokens.output_mean) == (1000.0, 30.0)
    assert METRICS.exam_cost_usd == pytest.approx(0.006)
    assert METRICS.spent_usd == pytest.approx(0.005)  # delivery-002 came from the local cache
    assert (METRICS.summary_words_median, METRICS.summary_words_max) == (8.0, 10)


def test_a_run_without_valid_cases_has_no_metrics():
    edition = make_edition([case_data(id="delivery-001")])
    record = run_record(
        [case_result("delivery-001", status=LLMStatus.ERROR, category=None, summary=None)]
    )
    with pytest.raises(ValueError, match="without valid cases"):
        compute_metrics(score_run(edition, record))
