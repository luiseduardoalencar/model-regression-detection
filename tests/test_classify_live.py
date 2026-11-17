"""One real classification with prompt v1. Spends money: run on purpose with `-m live`.

The email is invented and outside the golden set (no model output on golden cases before
the intra-annotator check, step 10).
"""

import pytest

from regression_detector.adapters.openai_client import OpenAIClient, build_async_openai
from regression_detector.feature.classifier import classify
from regression_detector.ports.llm import LLMStatus
from regression_detector.pricing import load_price_table
from regression_detector.prompts.loader import load_active_classifier

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

EMAIL = (
    "Boa noite. Comprei uma garrafa térmica no pedido 90417 há dez dias e o prazo já passou. "
    "O site só mostra 'pedido faturado'. Onde está a minha encomenda?"
)


async def test_prompt_v1_classifies_an_invented_email():
    prompt = load_active_classifier()
    client = OpenAIClient(build_async_openai())
    first = await classify(EMAIL, prompt.config, client)
    second = await classify(EMAIL, prompt.config, client)  # same prefix: may hit the cache
    cost = load_price_table().cost_usd(first.requested_model, first.usage)
    for result in (first, second):
        print(
            f"\nstatus={result.status} parsed={result.parsed} served={result.served_model} "
            f"usage={result.usage} latency_ms={result.latency_ms:.0f}"
        )
    print(f"prompt={prompt.version_id} sha256={prompt.sha256[:12]} cost_first_usd={cost:.6f}")

    assert first.status is LLMStatus.COMPLETED, first.detail
    assert first.parsed is not None
    assert first.parsed.summary.startswith("Cliente")
    assert first.usage.input_tokens >= 1024  # long enough for the provider's prompt cache
