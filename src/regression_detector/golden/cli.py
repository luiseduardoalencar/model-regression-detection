"""`uv run validate-golden [path]`: validate a golden edition and list its flags."""

import argparse
from pathlib import Path

from pydantic import ValidationError

from regression_detector.golden.schema import Difficulty, Language, load_edition
from regression_detector.golden.validation import Severity, coverage_summary, validate

DEFAULT_PATH = Path("golden/drafts/edition-1.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a golden set edition file.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    if not args.path.is_file():
        parser.error(f"file not found: {args.path}")

    try:
        edition = load_edition(args.path)
    except ValidationError as error:
        print(f"{args.path}: invalid file\n{error}")
        return 1

    flags = validate(edition)
    for flag in flags:
        ids = f" [{', '.join(flag.case_ids)}]" if flag.case_ids else ""
        print(f"{flag.severity.upper():<5} {flag.kind}{ids}: {flag.message}")

    print("\nCoverage (information only)")
    for summary in coverage_summary(edition):
        languages = ", ".join(f"{lang} {summary.languages[lang]}" for lang in Language)
        levels = ", ".join(f"{level} {summary.difficulties[level]}" for level in Difficulty)
        print(f"  {summary.case_type:<12} n={summary.total:<4} {languages} | {levels}")

    blocking = sum(flag.severity == Severity.BLOCK for flag in flags)
    print(f"\n{len(flags)} flags, {blocking} blocking")
    return 1 if blocking else 0
