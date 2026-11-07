"""Schema of a golden set edition file (planning §4, decisions 2.1-2.3)."""

from collections import Counter
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from regression_detector.feature.models import Category


class CaseType(StrEnum):
    """Coverage bucket of a case (decision 2.1)."""

    TYPICAL = "typical"
    EDGE = "edge"
    ADVERSARIAL = "adversarial"
    KNOWN_FAILURE = "known_failure"


class Difficulty(StrEnum):
    """Expected difficulty from the rubric (decision 2.3)."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Language(StrEnum):
    """Language of the email; metadata for slicing, not a category."""

    PT = "pt"
    EN = "en"
    MIXED = "mixed"


class EdgeType(StrEnum):
    """Edge and adversarial types (decision 2.2)."""

    AMBIGUOUS = "ambiguous"
    TEMPORAL = "temporal"
    NEGATION = "negation"
    CONFOUNDER = "confounder"
    MULTIPLE_REQUESTS = "multiple_requests"
    VERY_SHORT = "very_short"
    LONG_THREAD = "long_thread"
    TYPOS = "typos"
    SARCASM = "sarcasm"
    MIXED_LANGUAGE = "mixed_language"
    PROMPT_INJECTION = "prompt_injection"
    LABEL_FORCING = "label_forcing"
    OUT_OF_SCOPE = "out_of_scope"


ADVERSARIAL_TYPES = frozenset(
    {EdgeType.PROMPT_INJECTION, EdgeType.LABEL_FORCING, EdgeType.OUT_OF_SCOPE}
)

CASE_ID_PATTERN = r"^(" + "|".join(Category) + r")-\d{3}$"


class GoldenCase(BaseModel):
    """One exam question: an email and its answer key."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=CASE_ID_PATTERN)
    input_email: str = Field(min_length=1)
    expected_category: Category
    acceptable_categories: list[Category]
    expected_summary: str = Field(min_length=1)
    expected_difficulty: Difficulty
    case_type: CaseType
    language: Language
    edge_types: list[EdgeType]
    notes: str

    @model_validator(mode="after")
    def acceptable_excludes_expected(self) -> Self:
        if self.expected_category in self.acceptable_categories:
            raise ValueError("acceptable_categories must not repeat expected_category")
        return self


class QualityChecks(BaseModel):
    """Results of the label audit and the intra-annotator check, filled before freezing."""

    model_config = ConfigDict(extra="forbid")

    label_audit: dict[str, Any] | None
    intra_annotator: dict[str, Any] | None


class GoldenEdition(BaseModel):
    """A golden set edition: header plus cases."""

    model_config = ConfigDict(extra="forbid")

    edition: int = Field(ge=1)
    status: Literal["draft", "frozen"]
    created_at: date | None
    categories: list[Category]
    quality_checks: QualityChecks
    cases: list[GoldenCase]

    @model_validator(mode="after")
    def header_and_ids_are_consistent(self) -> Self:
        if self.categories != list(Category):
            raise ValueError("categories must list the Category labels, in order")
        id_counts = Counter(case.id for case in self.cases)
        repeated = sorted(case_id for case_id, count in id_counts.items() if count > 1)
        if repeated:
            raise ValueError(f"repeated case ids: {', '.join(repeated)}")
        return self


def load_edition(path: Path) -> GoldenEdition:
    """Read and validate an edition file."""
    return GoldenEdition.model_validate_json(path.read_text(encoding="utf-8"))
