"""The classify command: what it prints and its exit code, with a fake client."""

import io
from pathlib import Path

import yaml

from regression_detector.feature.cli import main
from regression_detector.ports.llm import LLMResult, LLMStatus, Usage
from tests.factories import prompt_data
from tests.test_classifier import FakeLLMClient


def test_prints_category_summary_cost_and_prompt_identity(capsys):
    assert main(["Meu pedido 222 não chegou."], client=FakeLLMClient()) == 0
    out = capsys.readouterr().out
    assert "prompt:   classifier v1 (sha256 " in out
    assert "category: delivery" in out
    assert "summary:  Cliente pergunta." in out
    assert "tokens:   input 2000 (cached 1536), output 40" in out
    # 464 x 0.10 + 1536 x 0.01 + 40 x 0.50 per 1M tokens
    assert "cost:     US$ 0.000082" in out


def test_reads_the_email_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("Meu pedido 222 não chegou.\n"))
    client = FakeLLMClient()
    assert main([], client=client) == 0
    assert client.requests[0].user_input == "<email>\nMeu pedido 222 não chegou.\n</email>"


def test_a_model_outcome_other_than_completed_exits_one(capsys):
    class RefusingClient:
        async def complete(self, request):
            return LLMResult(
                status=LLMStatus.REFUSAL,
                parsed=None,
                raw_text=None,
                requested_model=request.model,
                served_model=request.model,
                usage=Usage(),
                latency_ms=5.0,
                provider_request_id=None,
                detail="não posso ajudar",
            )

    assert main(["texto"], client=RefusingClient()) == 1
    assert "status:   refusal (não posso ajudar)" in capsys.readouterr().out


def test_an_invalid_prompt_file_stops_before_any_call(tmp_path: Path, capsys):
    path = tmp_path / "v1.yaml"
    path.write_text(yaml.safe_dump(prompt_data(version_id="v2"), sort_keys=False), "utf-8")
    client = FakeLLMClient()
    assert main(["texto", "--prompt", str(path)], client=client) == 1
    assert "configuration error" in capsys.readouterr().out
    assert client.requests == []


def test_a_model_without_price_stops_before_any_call(tmp_path: Path, capsys):
    path = tmp_path / "v1.yaml"
    path.write_text(yaml.safe_dump(prompt_data(model="gpt-unknown"), sort_keys=False), "utf-8")
    client = FakeLLMClient()
    assert main(["texto", "--prompt", str(path)], client=client) == 1
    assert "has no price in the price table" in capsys.readouterr().out
    assert client.requests == []
