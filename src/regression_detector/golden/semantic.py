"""Semantic near-duplicates: cosine similarity of embeddings (decision 2.6)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict

from regression_detector.ports.embeddings import EmbeddingClient, EmbeddingResult

SEMANTIC_WARN_SCORE = 0.74
DEFAULT_EMBEDDINGS_CONFIG = Path("config/embeddings.yaml")


class EmbeddingsConfig(BaseModel):
    """The contents of `config/embeddings.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str


@dataclass(frozen=True)
class SemanticPair:
    first_id: str
    second_id: str
    score: float


def load_embeddings_config(path: Path = DEFAULT_EMBEDDINGS_CONFIG) -> EmbeddingsConfig:
    with path.open(encoding="utf-8") as file:
        return EmbeddingsConfig.model_validate(yaml.safe_load(file))


async def embed_texts(
    client: EmbeddingClient, model: str, texts: Mapping[str, str]
) -> tuple[dict[str, tuple[float, ...]], EmbeddingResult]:
    """One vector per id, plus the call result (for its usage and served model)."""
    ids = list(texts)
    result = await client.embed(model, [texts[text_id] for text_id in ids])
    return dict(zip(ids, result.vectors, strict=True)), result


def cosine_matrix(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    """Cosine of every pair of vectors: 1 = same direction, 0 = unrelated."""
    matrix = np.asarray(vectors, dtype=float)
    unit = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    return unit @ unit.T


def find_semantic_pairs(
    vectors: Mapping[str, Sequence[float]], threshold: float = SEMANTIC_WARN_SCORE
) -> list[SemanticPair]:
    """Pairs of ids whose cosine reaches the threshold, highest score first."""
    ids = list(vectors)
    scores = cosine_matrix([vectors[text_id] for text_id in ids])
    rows, columns = np.triu_indices(len(ids), k=1)
    pairs = [
        SemanticPair(ids[row], ids[column], float(scores[row, column]))
        for row, column in zip(rows, columns, strict=True)
        if scores[row, column] >= threshold
    ]
    return sorted(pairs, key=lambda pair: pair.score, reverse=True)
