"""Prompt loader: valid files load with their identity, invalid ones never reach a run."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from regression_detector.feature.models import Category
from regression_detector.prompts.loader import (
    PromptFileError,
    load_active_classifier,
    load_classifier_prompt,
)
from tests.factories import prompt_data


def write_prompt(folder: Path, data: Any, name: str = "v1.yaml") -> Path:
    path = folder / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_valid_file_loads_with_version_and_hash(tmp_path):
    path = write_prompt(tmp_path, prompt_data())
    prompt = load_classifier_prompt(path)
    assert prompt.version_id == "v1"
    assert prompt.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert list(prompt.config.categories) == list(Category)
    assert prompt.config.generation.to_params().temperature == 0


def test_any_byte_change_changes_the_hash(tmp_path):
    first = load_classifier_prompt(write_prompt(tmp_path, prompt_data()))
    second = load_classifier_prompt(write_prompt(tmp_path, prompt_data(change_note="Other.")))
    assert first.sha256 != second.sha256


def reversed_categories() -> dict[str, str]:
    return {category.value: "definição" for category in reversed(Category)}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param(
            {"generation": {"reasoning_effort": "low", "temperature": 0, "max_output_tokens": 200}},
            "temperature is only accepted",
            id="temperature with reasoning effort low",
        ),
        pytest.param(
            {"categories": {"delivery": "só uma"}},
            "every Category label",
            id="missing categories",
        ),
        pytest.param(
            {"categories": reversed_categories()}, "in enum order", id="categories out of order"
        ),
        pytest.param(
            {"categories": prompt_data()["categories"] | {"shipping": "nova"}},
            "categories",
            id="unknown category",
        ),
        pytest.param(
            {"system_prompt": "Sem marcador de categorias. {tie_break_rules}"},
            "{categories} once, found 0",
            id="placeholder missing",
        ),
        pytest.param(
            {"system_prompt": "{categories} {categories} {tie_break_rules}"},
            "{categories} once, found 2",
            id="placeholder twice",
        ),
        pytest.param(
            {"few_shot_examples": [{"email": "x", "category": "shipping", "summary": "y"}]},
            "few_shot_examples",
            id="example with unknown category",
        ),
        pytest.param({"few_shot_examples": []}, "few_shot_examples", id="no examples"),
        pytest.param({"temperature": 0}, "Extra inputs", id="unknown key"),
        pytest.param({"version_id": "1"}, "version_id", id="bad version format"),
    ],
)
def test_invalid_contents_are_rejected(tmp_path, overrides, message):
    with pytest.raises(PromptFileError, match="invalid contents") as error:
        load_classifier_prompt(write_prompt(tmp_path, prompt_data(**overrides)))
    assert message in str(error.value)


def test_temperature_may_be_left_out_with_another_effort(tmp_path):
    generation = {"reasoning_effort": "low", "max_output_tokens": 500}
    prompt = load_classifier_prompt(write_prompt(tmp_path, prompt_data(generation=generation)))
    assert prompt.config.generation.temperature is None


def test_version_id_must_match_the_file_name(tmp_path):
    path = write_prompt(tmp_path, prompt_data(version_id="v2"), name="v1.yaml")
    with pytest.raises(PromptFileError, match="does not match the file name"):
        load_classifier_prompt(path)


def test_broken_yaml_is_rejected(tmp_path):
    path = tmp_path / "v1.yaml"
    path.write_text("version_id: [v1\n", encoding="utf-8")
    with pytest.raises(PromptFileError, match="not valid YAML"):
        load_classifier_prompt(path)


def test_yaml_with_python_tags_is_rejected(tmp_path):
    path = tmp_path / "v1.yaml"
    path.write_text("!!python/object/apply:os.system ['echo hacked']\n", encoding="utf-8")
    with pytest.raises(PromptFileError, match="not valid YAML"):
        load_classifier_prompt(path)


def test_a_list_is_not_a_prompt_file(tmp_path):
    with pytest.raises(PromptFileError, match="must be a YAML mapping"):
        load_classifier_prompt(write_prompt(tmp_path, ["v1"]))


def test_missing_file_is_a_prompt_error(tmp_path):
    with pytest.raises(PromptFileError, match="cannot be read"):
        load_classifier_prompt(tmp_path / "v9.yaml")


def test_active_pointer_selects_the_version(tmp_path):
    (tmp_path / "classifier").mkdir()
    write_prompt(tmp_path / "classifier", prompt_data())
    write_prompt(tmp_path / "classifier", prompt_data(version_id="v2"), name="v2.yaml")
    write_prompt(tmp_path, {"classifier": "v2"}, name="active.yaml")
    assert load_active_classifier(tmp_path).version_id == "v2"


def test_active_pointer_to_a_missing_version_fails(tmp_path):
    (tmp_path / "classifier").mkdir()
    write_prompt(tmp_path, {"classifier": "v7"}, name="active.yaml")
    with pytest.raises(PromptFileError, match="v7.yaml: cannot be read"):
        load_active_classifier(tmp_path)


def test_active_pointer_rejects_unknown_keys(tmp_path):
    write_prompt(tmp_path, {"classifier": "v1", "summarizer": "v1"}, name="active.yaml")
    with pytest.raises(PromptFileError, match="active.yaml: invalid contents"):
        load_active_classifier(tmp_path)
