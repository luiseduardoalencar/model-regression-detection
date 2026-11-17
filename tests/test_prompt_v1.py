"""The published classifier prompt v1 itself: what Luis approved stays true (decisions 1.2-1.4)."""

import re
from pathlib import Path

from regression_detector.feature.classifier import build_request
from regression_detector.feature.models import Category
from regression_detector.pricing import load_price_table
from regression_detector.prompts.loader import load_active_classifier, load_classifier_prompt

V1_PATH = Path("prompts/classifier/v1.yaml")
TAXONOMY_V1 = Path("config/taxonomy/v1.md")


def flat(text: str) -> str:
    """Whitespace collapsed, so line breaks in YAML and Markdown do not matter."""
    return re.sub(r"\s+", " ", text).strip()


def test_active_prompt_is_v1():
    assert load_active_classifier().version_id == "v1"


def test_generation_parameters_match_decision_1_2():
    config = load_classifier_prompt(V1_PATH).config
    assert config.model == "gpt-6-luna"
    assert config.generation.reasoning_effort == "none"
    assert config.generation.temperature == 0
    assert config.generation.max_output_tokens == 200
    load_price_table().price_for(config.model)


def test_one_example_per_category_in_enum_order():
    examples = load_classifier_prompt(V1_PATH).config.few_shot_examples
    assert [example.category for example in examples] == list(Category)


def test_definitions_and_tie_break_rules_are_copied_from_taxonomy_v1():
    config = load_classifier_prompt(V1_PATH).config
    taxonomy = flat(TAXONOMY_V1.read_text(encoding="utf-8"))
    for label, definition in config.categories.items():
        assert flat(f"- `{label}` — {definition}") in taxonomy, label
    for rule in config.tie_break_rules:
        assert flat(f"- {rule}") in taxonomy, rule[:40]
    assert taxonomy.count(" × ") == len(config.tie_break_rules)


def test_example_summaries_follow_rule_1_of_the_summary_guide():
    for example in load_classifier_prompt(V1_PATH).config.few_shot_examples:
        assert example.summary.startswith("Cliente "), example.summary


def test_rendered_instructions_have_no_placeholder_left():
    request = build_request(load_classifier_prompt(V1_PATH).config, "teste")
    assert "{" not in request.instructions
    assert "<email>" in request.instructions
