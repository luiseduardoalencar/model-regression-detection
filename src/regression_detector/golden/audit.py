"""LLM label audit (decision 2.5a): 3 prompt variants re-label every case; Luis decides."""

import asyncio
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from regression_detector.feature.models import Category
from regression_detector.golden.schema import GoldenCase, GoldenEdition
from regression_detector.ports.llm import (
    GenerationParams,
    LLMClient,
    LLMConfigurationError,
    LLMRequest,
    LLMStatus,
    Usage,
)

DEFAULT_VARIANTS_DIR = Path("config/label-audit")
DEFAULT_TAXONOMY_PATH = Path("config/taxonomy/v1.md")
TAXONOMY_PLACEHOLDER = "{taxonomy}"
VARIANT_COUNT = 3
DEFAULT_CONCURRENCY = 8


class AuditAnswer(BaseModel):
    """What each variant must return (strict JSON schema)."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    justification: str


class AuditVariant(BaseModel):
    """One prompt variant, read from `config/label-audit/<name>.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    model: str
    reasoning_effort: str
    max_output_tokens: int = Field(gt=0)
    instructions: str


class AuditOutcome(StrEnum):
    FLAGGED = "flagged"  # the variants agree with each other and disagree with Luis
    CONFIRMED = "confirmed"  # the variants agree with Luis (expected or acceptable)
    NO_CONSENSUS = "no_consensus"  # the variants disagree with each other
    NOT_AUDITED = "not_audited"  # at least one variant gave no valid answer


@dataclass(frozen=True)
class VariantAnswer:
    variant: str
    status: LLMStatus
    category: Category | None
    justification: str | None
    detail: str | None


@dataclass(frozen=True)
class CaseAudit:
    case_id: str
    outcome: AuditOutcome
    audit_category: Category | None
    answers: tuple[VariantAnswer, ...]


@dataclass(frozen=True)
class AuditReport:
    cases: tuple[CaseAudit, ...]
    usage_by_model: dict[str, Usage]

    def count(self, outcome: AuditOutcome) -> int:
        return sum(case.outcome == outcome for case in self.cases)

    def ids(self, outcome: AuditOutcome) -> list[str]:
        return [case.case_id for case in self.cases if case.outcome == outcome]


def load_variants(
    folder: Path = DEFAULT_VARIANTS_DIR, taxonomy_path: Path = DEFAULT_TAXONOMY_PATH
) -> tuple[AuditVariant, ...]:
    """The variants, each with the taxonomy text placed where `{taxonomy}` appears."""
    taxonomy = taxonomy_path.read_text(encoding="utf-8").strip()
    variants = []
    for path in sorted(folder.glob("*.yaml")):
        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
        instructions = data.get("instructions", "")
        if instructions.count(TAXONOMY_PLACEHOLDER) != 1:
            raise ValueError(f"{path}: instructions must contain {TAXONOMY_PLACEHOLDER} once")
        data["instructions"] = instructions.replace(TAXONOMY_PLACEHOLDER, taxonomy)
        variants.append(AuditVariant(name=path.stem, **data))
    if len(variants) != VARIANT_COUNT:
        raise ValueError(f"{folder}: expected {VARIANT_COUNT} variants, found {len(variants)}")
    return tuple(variants)


def decide(case: GoldenCase, answers: tuple[VariantAnswer, ...]) -> CaseAudit:
    """Flag rule of decision 2.5a: unanimous variants that disagree with Luis's labels."""
    if any(answer.status != LLMStatus.COMPLETED for answer in answers):
        return CaseAudit(case.id, AuditOutcome.NOT_AUDITED, None, answers)
    categories = {answer.category for answer in answers}
    if len(categories) != 1:
        return CaseAudit(case.id, AuditOutcome.NO_CONSENSUS, None, answers)
    category = categories.pop()
    accepted = {case.expected_category, *case.acceptable_categories}
    outcome = AuditOutcome.CONFIRMED if category in accepted else AuditOutcome.FLAGGED
    return CaseAudit(case.id, outcome, category, answers)


async def audit_edition(
    edition: GoldenEdition,
    variants: tuple[AuditVariant, ...],
    client: LLMClient,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> AuditReport:
    """Ask every variant about every case, at most `concurrency` calls at a time."""
    semaphore = asyncio.Semaphore(concurrency)
    usage: dict[str, Counter[str]] = {variant.model: Counter() for variant in variants}

    async def ask(case: GoldenCase, variant: AuditVariant) -> VariantAnswer:
        request = LLMRequest(
            model=variant.model,
            instructions=variant.instructions,
            user_input=case.input_email,
            output_schema=AuditAnswer,
            generation=GenerationParams(
                reasoning_effort=variant.reasoning_effort,
                max_output_tokens=variant.max_output_tokens,
            ),
        )
        async with semaphore:
            result = await client.complete(request)
        usage[variant.model].update(vars(result.usage))
        parsed = result.parsed
        return VariantAnswer(
            variant=variant.name,
            status=result.status,
            category=parsed.category if parsed else None,
            justification=parsed.justification if parsed else None,
            detail=result.detail,
        )

    async def audit_case(case: GoldenCase) -> CaseAudit:
        answers = await asyncio.gather(*(ask(case, variant) for variant in variants))
        return decide(case, tuple(answers))

    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(audit_case(case)) for case in edition.cases]
    except* LLMConfigurationError as errors:
        raise errors.exceptions[0] from None

    return AuditReport(
        cases=tuple(task.result() for task in tasks),
        usage_by_model={model: Usage(**counts) for model, counts in usage.items()},
    )
