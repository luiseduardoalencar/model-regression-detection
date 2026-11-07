"""Golden set validation: coverage matrix, edge-type rules and duplicates (2.1-2.3, 2.6)."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from regression_detector.feature.models import Category
from regression_detector.golden.dedup import MatchKind, find_pairs
from regression_detector.golden.schema import (
    ADVERSARIAL_TYPES,
    CaseType,
    Difficulty,
    EdgeType,
    GoldenEdition,
    Language,
)

CASES_PER_CATEGORY = {
    CaseType.TYPICAL: 14,
    CaseType.EDGE: 4,
    CaseType.ADVERSARIAL: 2,
    CaseType.KNOWN_FAILURE: 0,
}
MIN_HARD_CASES = 35
MIN_EDGE_TYPE_CASES = 2


class Severity(StrEnum):
    BLOCK = "block"
    WARN = "warn"


class FlagKind(StrEnum):
    LABEL_CONFLICT = "label_conflict"
    EXACT_DUPLICATE = "exact_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    SIMILAR_PAIR = "similar_pair"
    MATRIX_GAP = "matrix_gap"
    EDGE_TYPE_RULE = "edge_type_rule"


@dataclass(frozen=True)
class Flag:
    kind: FlagKind
    severity: Severity
    message: str
    case_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TypeSummary:
    case_type: CaseType
    total: int
    languages: Counter[Language]
    difficulties: Counter[Difficulty]


_PAIR_FLAGS = {
    MatchKind.EXACT: (FlagKind.EXACT_DUPLICATE, Severity.BLOCK),
    MatchKind.NEAR_DUPLICATE: (FlagKind.NEAR_DUPLICATE, Severity.BLOCK),
    MatchKind.SIMILAR: (FlagKind.SIMILAR_PAIR, Severity.WARN),
}


def validate(edition: GoldenEdition) -> list[Flag]:
    """All flags: label conflicts first, then blocking flags, then warnings."""
    flags = check_matrix(edition) + check_edge_types(edition) + check_duplicates(edition)
    return sorted(
        flags,
        key=lambda flag: (flag.kind != FlagKind.LABEL_CONFLICT, flag.severity != Severity.BLOCK),
    )


def check_matrix(edition: GoldenEdition) -> list[Flag]:
    """Exact coverage targets of edition 1."""
    flags = []
    per_cell = Counter((case.expected_category, case.case_type) for case in edition.cases)
    for category in Category:
        for case_type, expected in CASES_PER_CATEGORY.items():
            found = per_cell[(category, case_type)]
            if found != expected:
                flags.append(_gap(f"{category} has {found} {case_type} cases, expected {expected}"))

    hard = sum(case.expected_difficulty == Difficulty.HARD for case in edition.cases)
    if hard < MIN_HARD_CASES:
        flags.append(_gap(f"{hard} hard cases, expected at least {MIN_HARD_CASES}"))

    edge_type_counts = Counter(
        edge_type
        for case in edition.cases
        if case.case_type == CaseType.EDGE
        for edge_type in case.edge_types
    )
    for edge_type in EdgeType:
        found = edge_type_counts[edge_type]
        if edge_type not in ADVERSARIAL_TYPES and found < MIN_EDGE_TYPE_CASES:
            flags.append(
                _gap(
                    f"edge type {edge_type} appears in {found} edge cases, "
                    f"expected at least {MIN_EDGE_TYPE_CASES}"
                )
            )
    return flags


def check_edge_types(edition: GoldenEdition) -> list[Flag]:
    """Each case type carries the edge types that decision 2.2 expects."""
    flags = []
    for case in edition.cases:
        adversarial = set(case.edge_types) & ADVERSARIAL_TYPES
        if case.case_type == CaseType.ADVERSARIAL:
            allowed = _allowed_adversarial_types(case.expected_category)
            if not adversarial or not adversarial <= allowed:
                expected = " or ".join(sorted(allowed))
                flags.append(_rule(case.id, f"adversarial case needs {expected}"))
        elif adversarial:
            found = ", ".join(sorted(adversarial))
            flags.append(_rule(case.id, f"{case.case_type} case has adversarial types: {found}"))
        elif case.case_type == CaseType.EDGE and not case.edge_types:
            flags.append(_rule(case.id, "edge case has no edge_types"))
    return flags


def check_duplicates(edition: GoldenEdition) -> list[Flag]:
    """Exact and lexical pairs of emails, plus label conflicts among them."""
    cases = {case.id: case for case in edition.cases}
    flags = []
    for pair in find_pairs({case.id: case.input_email for case in edition.cases}):
        ids = (pair.first_id, pair.second_id)
        kind, severity = _PAIR_FLAGS[pair.match.kind]
        flags.append(Flag(kind, severity, f"lexical score {pair.match.score:.0f}", ids))
        first, second = cases[pair.first_id], cases[pair.second_id]
        if first.expected_category != second.expected_category:
            labels = f"{first.expected_category} vs {second.expected_category}"
            flags.append(
                Flag(FlagKind.LABEL_CONFLICT, Severity.WARN, f"similar emails, {labels}", ids)
            )
    return flags


def coverage_summary(edition: GoldenEdition) -> list[TypeSummary]:
    """Language and difficulty per case type; information only, never flags."""
    summaries = []
    for case_type in CaseType:
        cases = [case for case in edition.cases if case.case_type == case_type]
        if cases:
            summaries.append(
                TypeSummary(
                    case_type=case_type,
                    total=len(cases),
                    languages=Counter(case.language for case in cases),
                    difficulties=Counter(case.expected_difficulty for case in cases),
                )
            )
    return summaries


def _allowed_adversarial_types(category: Category) -> set[EdgeType]:
    if category == Category.GENERAL:
        return {EdgeType.OUT_OF_SCOPE}
    return {EdgeType.PROMPT_INJECTION, EdgeType.LABEL_FORCING}


def _gap(message: str) -> Flag:
    return Flag(FlagKind.MATRIX_GAP, Severity.BLOCK, message)


def _rule(case_id: str, message: str) -> Flag:
    return Flag(FlagKind.EDGE_TYPE_RULE, Severity.BLOCK, message, (case_id,))
