"""Run validity (decision 1.6d): more than 2 % infrastructure errors makes a run inconclusive."""

import pytest

from regression_detector.eval.validity import RunValidity, assess_validity


@pytest.mark.parametrize(
    ("infra_errors", "total_cases", "expected"),
    [
        (0, 140, RunValidity.VALID),
        (2, 140, RunValidity.VALID),  # 1.4 %
        (3, 140, RunValidity.INCONCLUSIVE),  # 2.1 %, the case named in decision 1.6d
        (2, 100, RunValidity.VALID),  # exactly 2 % is not "more than"
        (3, 100, RunValidity.INCONCLUSIVE),
        (1, 1, RunValidity.INCONCLUSIVE),
    ],
)
def test_more_than_two_percent_is_inconclusive(infra_errors, total_cases, expected):
    assessment = assess_validity(infra_errors, total_cases)
    assert assessment.validity == expected
    assert (assessment.infra_errors, assessment.total_cases) == (infra_errors, total_cases)
    assert assessment.limit_percent == 2


@pytest.mark.parametrize(("infra_errors", "total_cases"), [(0, 0), (-1, 10), (11, 10)])
def test_impossible_counts_are_rejected(infra_errors, total_cases):
    with pytest.raises(ValueError):
        assess_validity(infra_errors, total_cases)
