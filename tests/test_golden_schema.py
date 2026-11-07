"""The golden file schema accepts the draft and rejects malformed cases."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from regression_detector.golden.schema import GoldenCase, GoldenEdition, load_edition
from tests.factories import case_data, edition_data

DRAFT = Path(__file__).resolve().parents[1] / "golden" / "drafts" / "edition-1.json"


def test_draft_edition_loads():
    edition = load_edition(DRAFT)
    assert edition.edition == 1
    assert len(edition.cases) == 140


def test_valid_case_is_accepted():
    GoldenCase.model_validate(case_data())


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"expected_category": "shipping"}, id="unknown category"),
        pytest.param({"id": "delivery-7"}, id="id without three digits"),
        pytest.param({"id": "shipping-007"}, id="id prefix is not a category"),
        pytest.param({"case_type": "weird"}, id="unknown case type"),
        pytest.param({"edge_types": ["sarcasmo"]}, id="unknown edge type"),
        pytest.param({"input_email": ""}, id="empty email"),
        pytest.param({"expected_categry": "delivery"}, id="misspelled key"),
        pytest.param({"acceptable_categories": ["delivery"]}, id="acceptable repeats expected"),
    ],
)
def test_invalid_case_is_rejected(overrides):
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(case_data(**overrides))


def test_missing_field_is_rejected():
    data = case_data()
    del data["notes"]
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(data)


def test_repeated_ids_are_rejected():
    data = edition_data([case_data(), case_data()])
    with pytest.raises(ValidationError, match="repeated case ids: delivery-001"):
        GoldenEdition.model_validate(data)


def test_header_categories_must_match_the_enum():
    data = edition_data([case_data()], categories=["delivery", "payment"])
    with pytest.raises(ValidationError, match="categories must list"):
        GoldenEdition.model_validate(data)
