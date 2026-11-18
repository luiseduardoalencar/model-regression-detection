"""Run validity (decision 1.6d): too many infrastructure errors make a run inconclusive.

The limit is an integer percentage read from `config/gate.yaml`
(`infra_error_limit_percent`, decided 2026-11-17 and 2026-11-18), so the
comparison is exact: with a limit of 2, 3 errors in 140 cases is inconclusive.
"""

from dataclasses import dataclass
from enum import StrEnum


class RunValidity(StrEnum):
    """Whether a run may produce a verdict."""

    VALID = "valid"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ValidityAssessment:
    """The verdict on a run's validity and the numbers behind it."""

    validity: RunValidity
    infra_errors: int
    total_cases: int
    limit_percent: int


def assess_validity(infra_errors: int, total_cases: int, limit_percent: int) -> ValidityAssessment:
    """Inconclusive when infra errors exceed `limit_percent` of the cases.

    The counts are passed in, so judge failures (build step 8) can join the same limit.
    """
    if total_cases <= 0:
        raise ValueError("a run needs at least one case")
    if not 0 <= infra_errors <= total_cases:
        raise ValueError("infra_errors must be between 0 and the number of cases")
    over_limit = infra_errors * 100 > limit_percent * total_cases
    return ValidityAssessment(
        validity=RunValidity.INCONCLUSIVE if over_limit else RunValidity.VALID,
        infra_errors=infra_errors,
        total_cases=total_cases,
        limit_percent=limit_percent,
    )
