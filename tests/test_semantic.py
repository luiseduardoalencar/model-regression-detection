"""Semantic layer with hand-made vectors: no network, no cost."""

import asyncio
from collections.abc import Sequence

import pytest

from regression_detector.golden.semantic import (
    cosine_matrix,
    embed_texts,
    find_semantic_pairs,
    load_embeddings_config,
)
from regression_detector.golden.validation import FlagKind, Severity, validate
from regression_detector.ports.embeddings import EmbeddingResult
from regression_detector.ports.llm import Usage
from tests.factories import case_data, full_matrix_cases, make_edition


def test_cosine_ignores_length_and_measures_direction():
    scores = cosine_matrix([[1.0, 0.0], [3.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
    assert scores[0, 1] == pytest.approx(1.0)  # same direction, different length
    assert scores[0, 2] == pytest.approx(0.0)  # perpendicular
    assert scores[0, 3] == pytest.approx(0.7071, abs=1e-4)  # 45 degrees


def test_pairs_at_or_above_the_threshold_are_found_highest_first():
    vectors = {"a": [1.0, 0.0], "b": [1.0, 0.1], "c": [1.0, 0.5], "d": [0.0, 1.0]}
    pairs = find_semantic_pairs(vectors, threshold=0.92)
    assert [(p.first_id, p.second_id) for p in pairs] == [("a", "b"), ("b", "c")]
    assert pairs[0].score > pairs[1].score >= 0.92


def test_embed_texts_keeps_each_vector_with_its_id():
    class FakeEmbeddingClient:
        async def embed(self, model: str, texts: Sequence[str]) -> EmbeddingResult:
            vectors = tuple((float(len(text)), 1.0) for text in texts)
            return EmbeddingResult(vectors, model, model, Usage(input_tokens=7), 1.0)

    vectors, result = asyncio.run(
        embed_texts(FakeEmbeddingClient(), "model-x", {"x": "ab", "y": "abcd"})
    )
    assert vectors == {"x": (2.0, 1.0), "y": (4.0, 1.0)}
    assert result.usage.input_tokens == 7


def test_versioned_embeddings_config_loads():
    assert load_embeddings_config().model == "text-embedding-3-large"


def vectors_for(cases, close_pairs=()):
    """Perpendicular vectors (cosine 0) except the given pairs, which get the same vector."""
    ids = [case["id"] for case in cases]
    vectors = {
        case_id: [1.0 if i == j else 0.0 for j in range(len(ids))] for i, case_id in enumerate(ids)
    }
    for first, second in close_pairs:
        vectors[second] = vectors[first]
    return vectors


def test_without_vectors_the_semantic_layer_is_skipped():
    cases = full_matrix_cases()
    assert validate(make_edition(cases)) == []


def test_semantic_pair_with_same_label_warns():
    cases = full_matrix_cases()
    flags = validate(make_edition(cases), vectors_for(cases, [("delivery-001", "delivery-002")]))
    assert [(f.kind, f.severity, f.case_ids) for f in flags] == [
        (FlagKind.SEMANTIC_PAIR, Severity.WARN, ("delivery-001", "delivery-002"))
    ]
    assert flags[0].message == "semantic score 1.000"


def test_semantic_pair_with_different_labels_is_also_a_label_conflict():
    cases = full_matrix_cases()
    flags = validate(make_edition(cases), vectors_for(cases, [("delivery-001", "payment-001")]))
    assert [f.kind for f in flags] == [FlagKind.LABEL_CONFLICT, FlagKind.SEMANTIC_PAIR]
    assert all(f.severity == Severity.WARN for f in flags)


def test_pair_already_caught_by_the_lexical_layer_is_not_repeated():
    email = "Meu pedido 12345 ainda não chegou e o rastreio está parado faz dias."
    cases = full_matrix_cases()
    cases[0] = case_data(**{**cases[0], "input_email": email})
    cases[1] = case_data(**{**cases[1], "input_email": email + "!"})
    flags = validate(make_edition(cases), vectors_for(cases, [(cases[0]["id"], cases[1]["id"])]))
    assert [f.kind for f in flags] == [FlagKind.EXACT_DUPLICATE]
