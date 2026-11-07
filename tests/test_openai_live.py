"""One real call to OpenAI. Spends money: run on purpose with `-m live`."""

import pytest

from regression_detector.adapters.openai_client import OpenAIClient, build_async_openai
from regression_detector.feature.models import EmailClassification
from regression_detector.ports.llm import GenerationParams, LLMRequest, LLMStatus
from regression_detector.pricing import load_price_table

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

MODEL = "gpt-6-luna"


async def test_real_call_classifies_an_invented_email():
    request = LLMRequest(
        model=MODEL,
        instructions=(
            "Classifique o email de cliente de uma loja online em uma categoria "
            "e escreva um resumo de uma frase em português."
        ),
        user_input="Olá, comprei um fone há duas semanas e até hoje não chegou. Cadê?",
        output_schema=EmailClassification,
        generation=GenerationParams(
            reasoning_effort="none", max_output_tokens=200, temperature=0.0
        ),
    )

    result = await OpenAIClient(build_async_openai()).complete(request)
    cost = load_price_table().cost_usd(request.model, result.usage)
    print(
        f"\nstatus={result.status} parsed={result.parsed} served={result.served_model} "
        f"usage={result.usage} latency_ms={result.latency_ms:.0f} cost_usd={cost:.6f} "
        f"request_id={result.provider_request_id}"
    )

    assert result.status is LLMStatus.COMPLETED, result.detail
    assert result.parsed is not None
    assert result.served_model is not None and result.served_model.startswith(MODEL)
    assert result.usage.input_tokens > 0
    assert cost > 0
