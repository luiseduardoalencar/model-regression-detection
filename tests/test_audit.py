"""Label audit rules and orchestration with a fake LLM client: no network, no cost."""

import asyncio
import json
from pathlib import Path

import pytest

from regression_detector.feature.models import Category
from regression_detector.golden.audit import (
    AuditAnswer,
    AuditOutcome,
    VariantAnswer,
    audit_edition,
    decide,
    load_variants,
)
from regression_detector.golden.audit_cli import main
from regression_detector.golden.schema import GoldenCase
from regression_detector.ports.llm import (
    LLMConfigurationError,
    LLMRequest,
    LLMResult,
    LLMStatus,
    Usage,
)
from tests.factories import case_data, edition_data, make_edition

D, P, R = Category.DELIVERY, Category.PAYMENT, Category.RETURN_REFUND


def answer(category: Category | None, status: LLMStatus = LLMStatus.COMPLETED) -> VariantAnswer:
    return VariantAnswer("v", status, category, "porque sim" if category else None, None)


def golden_case(**overrides) -> GoldenCase:
    return GoldenCase.model_validate(case_data(**overrides))


@pytest.mark.parametrize(
    ("answers", "outcome", "audit_category"),
    [
        ((P, P, P), AuditOutcome.FLAGGED, P),
        ((D, D, D), AuditOutcome.CONFIRMED, D),
        ((R, R, R), AuditOutcome.CONFIRMED, R),  # R is acceptable for this case
        ((P, P, D), AuditOutcome.NO_CONSENSUS, None),
    ],
)
def test_flag_rule(answers, outcome, audit_category):
    case = golden_case(expected_category="delivery", acceptable_categories=["return_refund"])
    audit = decide(case, tuple(answer(category) for category in answers))
    assert (audit.outcome, audit.audit_category) == (outcome, audit_category)


def test_a_variant_without_a_valid_answer_means_not_audited():
    answers = (answer(P), answer(P), answer(None, LLMStatus.REFUSAL))
    assert decide(golden_case(), answers).outcome == AuditOutcome.NOT_AUDITED


class FakeLLMClient:
    """Answers each variant with a fixed category per case id, and counts the calls."""

    def __init__(self, labels: dict[str, Category], error: Exception | None = None) -> None:
        self.labels = labels
        self.error = error
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        if self.error:
            raise self.error
        case_id = request.user_input.removeprefix("email ")
        parsed = AuditAnswer(category=self.labels[case_id], justification="trecho do email")
        return LLMResult(
            LLMStatus.COMPLETED,
            parsed,
            parsed.model_dump_json(),
            request.model,
            request.model,
            Usage(input_tokens=100, output_tokens=10),
            1.0,
            None,
        )


def two_cases() -> list[dict]:
    return [
        case_data(id="delivery-001", input_email="email delivery-001"),
        case_data(id="payment-001", input_email="email payment-001", expected_category="payment"),
    ]


def test_every_case_is_asked_to_every_variant():
    client = FakeLLMClient({"delivery-001": D, "payment-001": D})
    report = asyncio.run(audit_edition(make_edition(two_cases()), load_variants(), client))

    assert client.calls == 6
    assert report.ids(AuditOutcome.FLAGGED) == ["payment-001"]
    assert report.ids(AuditOutcome.CONFIRMED) == ["delivery-001"]
    assert report.usage_by_model["gpt-6.1-terra"] == Usage(input_tokens=600, output_tokens=60)


def test_configuration_error_stops_the_audit():
    client = FakeLLMClient({}, error=LLMConfigurationError("bad key"))
    with pytest.raises(LLMConfigurationError, match="bad key"):
        asyncio.run(audit_edition(make_edition(two_cases()), load_variants(), client))


def test_versioned_variants_load_with_the_taxonomy():
    variants = load_variants()
    assert [v.name for v in variants] == ["variant-a", "variant-b", "variant-c"]
    assert all("Regras de desempate" in v.instructions for v in variants)
    assert all("{taxonomy}" not in v.instructions for v in variants)


def test_variant_without_the_placeholder_is_refused(tmp_path):
    taxonomy = tmp_path / "taxonomy.md"
    taxonomy.write_text("taxonomia", encoding="utf-8")
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.yaml").write_text(
            "model: m\nreasoning_effort: low\nmax_output_tokens: 10\ninstructions: sem marcador\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="taxonomy"):
        load_variants(tmp_path, taxonomy)


def test_command_prints_ids_but_never_labels(tmp_path, capsys):
    golden = tmp_path / "edition.json"
    golden.write_text(json.dumps(edition_data(two_cases())), encoding="utf-8")
    output = tmp_path / "audit.json"
    client = FakeLLMClient({"delivery-001": D, "payment-001": D})

    assert main([str(golden), "--output", str(output)], llm_client=client) == 0

    printed = capsys.readouterr().out
    assert "flagged ids: payment-001" in printed
    assert "delivery" not in printed.replace("delivery-001", "")
    report = json.loads(Path(output).read_text(encoding="utf-8"))
    assert report["summary"]["flagged"] == 1
    assert report["cases"][0]["case_id"] == "payment-001"
    assert report["cases"][0]["audit_category"] == "delivery"
