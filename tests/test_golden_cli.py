"""The validate-golden command: what it prints and its exit code."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from regression_detector.golden.cli import main
from regression_detector.ports.embeddings import EmbeddingResult, EmbeddingUnavailableError
from regression_detector.ports.llm import Usage
from tests.factories import case_data, edition_data, full_matrix_cases, prompt_data


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


def test_few_shot_of_the_active_prompt_is_checked(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path]) == 0
    assert "few-shot: classifier v1, 7 examples" in capsys.readouterr().out


def test_few_shot_equal_to_a_golden_email_blocks(tmp_path, capsys):
    prompt = tmp_path / "v1.yaml"
    example = {"email": "email delivery-001", "category": "delivery", "summary": "Cliente."}
    prompt.write_text(
        yaml.safe_dump(prompt_data(few_shot_examples=[example]), sort_keys=False), "utf-8"
    )
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path, "--prompt", str(prompt)]) == 1
    out = capsys.readouterr().out
    assert "BLOCK few_shot_overlap [v1:few-shot-1, delivery-001]: exact" in out


def test_invalid_prompt_file_exits_one(tmp_path, capsys):
    prompt = tmp_path / "v1.yaml"
    prompt.write_text("version_id: [v1\n", encoding="utf-8")
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path, "--prompt", str(prompt)]) == 1
    assert "configuration error" in capsys.readouterr().out


def test_examples_are_embedded_with_the_golden_emails(tmp_path):
    class CountingClient(FakeEmbeddingClient):
        async def embed(self, model, texts):
            self.count = len(texts)
            return await super().embed(model, texts)

    client = CountingClient()
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path], embedding_client=client) == 0
    assert client.count == 140 + 7
