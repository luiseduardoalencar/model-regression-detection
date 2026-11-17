"""`uv run classify "<email>"`: classify one email with the active classifier prompt."""

import argparse
import asyncio
import sys
from pathlib import Path

from regression_detector.feature.classifier import classify
from regression_detector.ports.llm import LLMClient, LLMConfigurationError, LLMStatus
from regression_detector.pricing import load_price_table
from regression_detector.prompts.loader import (
    LoadedPrompt,
    PromptFileError,
    load_active_classifier,
    load_classifier_prompt,
)


def main(argv: list[str] | None = None, client: LLMClient | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify one support email.")
    parser.add_argument("email", nargs="?", help="the email text; read from stdin when omitted")
    parser.add_argument(
        "--prompt", type=Path, help="a classifier prompt file (default: prompts/active.yaml)"
    )
    args = parser.parse_args(argv)
    email = args.email if args.email is not None else sys.stdin.read()
    if not email.strip():
        parser.error("the email is empty")

    try:
        prompt = load_classifier_prompt(args.prompt) if args.prompt else load_active_classifier()
        price_table = load_price_table()
        price_table.price_for(prompt.config.model)
        if client is None:
            client = _openai_client()
        result = asyncio.run(classify(email, prompt.config, client))
    except (PromptFileError, LLMConfigurationError) as error:
        print(f"configuration error: {error}")
        return 1

    print(_prompt_line(prompt))
    print(f"status:   {result.status}" + (f" ({result.detail})" if result.detail else ""))
    if result.parsed is not None:
        print(f"category: {result.parsed.category}")
        print(f"summary:  {result.parsed.summary}")
    elif result.raw_text:
        print(f"raw text: {result.raw_text}")
    usage = result.usage
    cost = price_table.cost_usd(result.requested_model, usage)
    print(f"model:    {result.requested_model} (served: {result.served_model})")
    print(
        f"tokens:   input {usage.input_tokens} (cached {usage.cached_input_tokens}), "
        f"output {usage.output_tokens}"
    )
    print(f"cost:     US$ {cost:.6f}")
    print(f"latency:  {result.latency_ms:.0f} ms")
    return 0 if result.status == LLMStatus.COMPLETED else 1


def _prompt_line(prompt: LoadedPrompt) -> str:
    return f"prompt:   classifier {prompt.version_id} (sha256 {prompt.sha256[:12]})"


def _openai_client() -> LLMClient:
    # Entry point, so it may pick the adapter; the vendor SDK is imported only here.
    from regression_detector.adapters.openai_client import OpenAIClient, build_async_openai

    return OpenAIClient(build_async_openai())
