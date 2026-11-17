"""The feature under test: route a support email to a queue and summarize it (decision 1.1)."""

from regression_detector.feature.models import EmailClassification
from regression_detector.feature.prompt_config import (
    CATEGORIES_PLACEHOLDER,
    TIE_BREAK_RULES_PLACEHOLDER,
    PromptConfig,
)
from regression_detector.ports.llm import FewShotExample, LLMClient, LLMRequest, LLMResult

EMAIL_OPEN = "<email>"
EMAIL_CLOSE = "</email>"


def wrap_email(email: str) -> str:
    """Mark the email as data, not instructions (spotlighting by delimiting, decided 2026-11-16)."""
    return f"{EMAIL_OPEN}\n{email.strip()}\n{EMAIL_CLOSE}"


def render_instructions(config: PromptConfig) -> str:
    """The system prompt with the category definitions and tie-break rules filled in."""
    categories = "\n".join(
        f"- `{label}` — {definition.strip()}" for label, definition in config.categories.items()
    )
    rules = "\n".join(f"- {rule.strip()}" for rule in config.tie_break_rules)
    return (
        config.system_prompt.replace(CATEGORIES_PLACEHOLDER, categories)
        .replace(TIE_BREAK_RULES_PLACEHOLDER, rules)
        .strip()
    )


def build_request(config: PromptConfig, email: str) -> LLMRequest[EmailClassification]:
    """Everything the model receives: only the prompt and the email, never the answer key."""
    examples = tuple(
        FewShotExample(
            input_text=wrap_email(example.email),
            output_text=EmailClassification(
                category=example.category, summary=example.summary.strip()
            ).model_dump_json(),
        )
        for example in config.few_shot_examples
    )
    return LLMRequest(
        model=config.model,
        instructions=render_instructions(config),
        user_input=wrap_email(email),
        output_schema=EmailClassification,
        generation=config.generation.to_params(),
        few_shot_examples=examples,
    )


async def classify(
    email: str, config: PromptConfig, client: LLMClient
) -> LLMResult[EmailClassification]:
    """Classify one email; the result carries the status, usage and latency of the call."""
    return await client.complete(build_request(config, email))
