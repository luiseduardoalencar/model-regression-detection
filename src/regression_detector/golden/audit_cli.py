"""`uv run audit-labels [path]`: LLM label audit of a golden edition (decision 2.5a).

The terminal shows only counts and case IDs, never labels: the guide asks Luis
for his blind answer before he sees the audit label (no anchoring).
"""

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from regression_detector.golden.audit import (
    DEFAULT_TAXONOMY_PATH,
    DEFAULT_VARIANTS_DIR,
    AuditOutcome,
    AuditReport,
    AuditVariant,
    audit_edition,
    load_variants,
)
from regression_detector.golden.cli import DEFAULT_PATH
from regression_detector.golden.schema import load_edition
from regression_detector.ports.llm import LLMClient, LLMConfigurationError
from regression_detector.pricing import load_price_table

DEFAULT_OUTPUT = Path("golden/drafts/label-audit.json")


def main(argv: list[str] | None = None, llm_client: LLMClient | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM label audit of a golden set edition.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if not args.path.is_file():
        parser.error(f"file not found: {args.path}")

    try:
        edition = load_edition(args.path)
    except ValidationError as error:
        print(f"{args.path}: invalid file\n{error}")
        return 1

    try:
        variants = load_variants()
        price_table = load_price_table()
        for variant in variants:
            price_table.price_for(variant.model)
        client = llm_client or _openai_llm_client()
        report = asyncio.run(audit_edition(edition, variants, client))
    except (LLMConfigurationError, ValueError) as error:
        print(f"configuration error: {error}")
        return 1

    cost = sum(price_table.cost_usd(model, usage) for model, usage in report.usage_by_model.items())
    _write_report(args.output, args.path, variants, report, cost)

    calls = len(report.cases) * len(variants)
    print(f"Audited {len(report.cases)} cases with {len(variants)} variants ({calls} calls).")
    for outcome in AuditOutcome:
        print(f"  {outcome:<13} {report.count(outcome)}")
    for outcome in (AuditOutcome.FLAGGED, AuditOutcome.NOT_AUDITED):
        ids = report.ids(outcome)
        if ids:
            print(f"{outcome} ids: {', '.join(ids)}")
    print(f"Cost: US$ {cost:.4f}")
    print(f"Details in {args.output} (audit labels: open only through guides/label-audit.md)")
    return 1 if report.count(AuditOutcome.NOT_AUDITED) else 0


def _write_report(
    output: Path,
    golden_path: Path,
    variants: tuple[AuditVariant, ...],
    report: AuditReport,
    cost: float,
) -> None:
    order = list(AuditOutcome)
    cases = sorted(report.cases, key=lambda case: (order.index(case.outcome), case.case_id))
    data = {
        "audited_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "golden_file": str(golden_path),
        "taxonomy": str(DEFAULT_TAXONOMY_PATH),
        "variants": [
            {"name": v.name, "model": v.model, "reasoning_effort": v.reasoning_effort}
            for v in variants
        ],
        "variants_dir": str(DEFAULT_VARIANTS_DIR),
        "summary": {outcome.value: report.count(outcome) for outcome in AuditOutcome},
        "cost_usd": round(cost, 6),
        "cases": [asdict(case) for case in cases],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _openai_llm_client() -> LLMClient:
    # The command is an entry point, so it may pick the adapter.
    from regression_detector.adapters.openai_client import OpenAIClient, build_async_openai

    return OpenAIClient(build_async_openai())
