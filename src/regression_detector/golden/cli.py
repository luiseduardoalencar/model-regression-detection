"""`uv run validate-golden [path]`: validate a golden edition and list its flags."""

import argparse
import asyncio
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from regression_detector.golden.schema import (
    Difficulty,
    GoldenEdition,
    Language,
    load_edition,
)
from regression_detector.golden.semantic import embed_texts, load_embeddings_config
from regression_detector.golden.validation import Severity, coverage_summary, validate
from regression_detector.ports.embeddings import EmbeddingClient, EmbeddingUnavailableError
from regression_detector.ports.llm import LLMConfigurationError
from regression_detector.pricing import load_price_table

DEFAULT_PATH = Path("golden/drafts/edition-1.json")


def main(argv: list[str] | None = None, embedding_client: EmbeddingClient | None = None) -> int:
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

    try:
        vectors = _semantic_vectors(edition, embedding_client)
    except LLMConfigurationError as error:
        print(f"configuration error: {error}")
        return 1

    flags = validate(edition, vectors)
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


def _semantic_vectors(
    edition: GoldenEdition, client: EmbeddingClient | None
) -> dict[str, Sequence[float]] | None:
    """Embeddings of every email, or None (with a printed reason) when the layer is skipped."""
    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            print("semantic layer skipped: OPENAI_API_KEY not set\n")
            return None
        client = _openai_embedding_client()

    config = load_embeddings_config()
    price_table = load_price_table()
    price_table.price_for(config.model)
    texts = {case.id: case.input_email for case in edition.cases}
    try:
        vectors, result = asyncio.run(embed_texts(client, config.model, texts))
    except EmbeddingUnavailableError as error:
        print(f"semantic layer skipped: {error}\n")
        return None

    cost = price_table.cost_usd(config.model, result.usage)
    print(
        f"semantic layer: {result.served_model}, {result.usage.input_tokens} tokens, "
        f"US$ {cost:.6f}\n"
    )
    return vectors


def _openai_embedding_client() -> EmbeddingClient:
    # The command is an entry point, so it may pick the adapter; importing it here keeps
    # the vendor SDK unloaded when the layer is skipped.
    from regression_detector.adapters.openai_client import build_async_openai
    from regression_detector.adapters.openai_embeddings import OpenAIEmbeddingClient

    return OpenAIEmbeddingClient(build_async_openai())
