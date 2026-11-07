"""The validate-golden command: what it prints and its exit code."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from regression_detector.golden.cli import main
from regression_detector.ports.embeddings import EmbeddingResult, EmbeddingUnavailableError
from regression_detector.ports.llm import Usage
from tests.factories import case_data, edition_data, full_matrix_cases


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Tests never reach the real API, whatever the developer's environment holds."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


class FakeEmbeddingClient:
    """Gives each distinct text its own direction (cosine 0); identical texts share one."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def embed(self, model: str, texts: Sequence[str]) -> EmbeddingResult:
        if self.error:
            raise self.error
        vectors = tuple(tuple(1.0 if text == other else 0.0 for other in texts) for text in texts)
        return EmbeddingResult(vectors, model, model, Usage(input_tokens=1_000), 1.0)


def write_edition(folder: Path, data: dict[str, Any]) -> str:
    path = folder / "edition.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_complete_edition_exits_zero(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path]) == 0
    assert "0 flags, 0 blocking" in capsys.readouterr().out


def test_matrix_gap_exits_one(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data([case_data()]))
    assert main([path]) == 1
    assert "matrix_gap" in capsys.readouterr().out


def test_schema_error_exits_one(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data([case_data(expected_category="shipping")]))
    assert main([path]) == 1
    assert "expected_category" in capsys.readouterr().out


def test_without_api_key_the_semantic_layer_is_skipped(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path]) == 0
    assert "semantic layer skipped: OPENAI_API_KEY not set" in capsys.readouterr().out


def test_semantic_layer_runs_and_reports_its_cost(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path], embedding_client=FakeEmbeddingClient()) == 0
    out = capsys.readouterr().out
    # 1000 tokens x US$ 0.13 per 1M tokens
    assert "semantic layer: text-embedding-3-large, 1000 tokens, US$ 0.000130" in out


def test_unavailable_api_skips_the_semantic_layer_without_failing(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    client = FakeEmbeddingClient(error=EmbeddingUnavailableError("RateLimitError"))
    assert main([path], embedding_client=client) == 0
    assert "semantic layer skipped: RateLimitError" in capsys.readouterr().out
