"""Builders of golden cases and editions for the tests."""

from itertools import cycle
from typing import Any

from regression_detector.feature.models import Category
from regression_detector.golden.schema import ADVERSARIAL_TYPES, EdgeType, GoldenEdition


def case_data(**overrides: Any) -> dict[str, Any]:
    """A valid case as a JSON-like dict; keyword arguments replace fields."""
    data = {
        "id": "delivery-001",
        "input_email": "Meu pedido 12345 ainda não chegou e o rastreio está parado.",
        "expected_category": "delivery",
        "acceptable_categories": [],
        "expected_summary": "Cliente informa que o pedido 12345 não chegou e pede o rastreio.",
        "expected_difficulty": "easy",
        "case_type": "typical",
        "language": "pt",
        "edge_types": [],
        "notes": "Caso de teste.",
    }
    return data | overrides


def edition_data(cases: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    """A valid edition header around the given cases."""
    data = {
        "edition": 1,
        "status": "draft",
        "created_at": None,
        "categories": [category.value for category in Category],
        "quality_checks": {"label_audit": None, "intra_annotator": None},
        "cases": cases,
    }
    return data | overrides


def make_edition(cases: list[dict[str, Any]]) -> GoldenEdition:
    return GoldenEdition.model_validate(edition_data(cases))


def full_matrix_cases() -> list[dict[str, Any]]:
    """140 cases that meet every exact target of edition 1; the emails are placeholders."""
    edge_types = cycle([t.value for t in EdgeType if t not in ADVERSARIAL_TYPES])
    cases = []
    for category in Category:
        adversarial_type = "out_of_scope" if category == Category.GENERAL else "prompt_injection"
        for number in range(1, 21):
            if number <= 14:
                kind = {"case_type": "typical", "expected_difficulty": "medium", "edge_types": []}
            elif number <= 18:
                kind = {"case_type": "edge", "expected_difficulty": "hard"}
                kind["edge_types"] = [next(edge_types)]
            else:
                kind = {"case_type": "adversarial", "expected_difficulty": "hard"}
                kind["edge_types"] = [adversarial_type]
            case_id = f"{category}-{number:03d}"
            cases.append(
                case_data(
                    id=case_id,
                    input_email=f"email {case_id}",
                    expected_category=category.value,
                    **kind,
                )
            )
    return cases


def prompt_data(**overrides: Any) -> dict[str, Any]:
    """A valid classifier prompt file as a YAML-like dict; keyword arguments replace keys."""
    data = {
        "version_id": "v1",
        "created_at": "2026-11-16",
        "change_note": "Test prompt.",
        "model": "gpt-6-luna",
        "generation": {"reasoning_effort": "none", "temperature": 0, "max_output_tokens": 200},
        "categories": {category.value: f"definição de {category}" for category in Category},
        "tie_break_rules": ["`delivery` × `cancellation`: pede para cancelar → `cancellation`."],
        "system_prompt": "Classifique.\n\n{categories}\n\nDesempates:\n{tie_break_rules}\n",
        "few_shot_examples": [
            {
                "email": "Meu pedido 111 não chegou.",
                "category": "delivery",
                "summary": "Cliente pergunta pelo pedido 111.",
            }
        ],
    }
    return data | overrides
