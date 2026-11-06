# Phase 1 — Feature under test

**Goal:** a classifier that receives an email, calls the model with the
active prompt version and returns a validated JSON object, behind ports that
keep the core vendor-independent.

**Status:** all decisions taken (1.1–1.6). Not implemented yet.
Implementation checklist: [`planning.md` §7, Phase 1](../planning.md#phase-1--feature-under-test).

## 1.1 Output contract

**Decision.** The classifier returns
`EmailClassification { category: Category, summary: str }`, in that order.

- `category`: strict enum with the 7 labels (`delivery`, `cancellation`,
  `return_refund`, `payment`, `account`, `technical`, `general`).
- `summary`: one sentence in Portuguese, written per
  [`summary-guide.md`](../summary-guide.md). No hard length limit in the
  schema; summary length is recorded as a metric.
- No `reasoning` field and no `confidence` field in v1.
- Call metadata (latency, tokens, served model, prompt version) is not part of
  the contract; it lives in the result envelope (1.5).

**Why.**
- Constraining output to discrete labels tends to help classification (JSON
  beat free text on a 49-label task), while constraining free reasoning hurts
  it [1][2][3].
- Chain-of-thought helps mainly on math and logic [4]; on text
  classification it adds +1–3 points on large models at 10–100× the tokens
  and less stability, and few-shot examples help more than reasoning [5]; in
  financial sentiment, reasoning consistently degraded results [6].
- Verbalized confidence became more reliable only for flagship judges with a
  specific prompting recipe; it would require calibration measurement [7].
- Structured outputs generate keys in schema order [8], so field order is a
  design choice; `category` → `summary` is the conventional order.

**Future experiments (measured by the harness):** reasoning as a field or via
`reasoning.effort=low`; `summary` → `category` order (a hypothesis, no study
found).

## 1.2 Prompt file contents

**Decision.** Each `prompts/classifier/vN.yaml` holds the feature's full
runtime contract:

| Key | Content |
|---|---|
| `version_id`, `created_at`, `change_note` | Metadata; `change_note` in English, shown in the report and the PR comment |
| `model` | Model ID, e.g. `gpt-6-luna` |
| `generation` | `reasoning_effort: none`, `temperature: 0`, `max_output_tokens: 200` (also a cost cap) |
| `categories` | English label + Portuguese definition, rendered into the prompt; loader checks the 7 labels match the enum |
| `tie_break_rules` | Portuguese, rendered into the prompt |
| `system_prompt` | Portuguese template |
| `few_shot_examples` | See 1.4 |

The loader rejects `temperature` combined with any reasoning effort other
than `none` (OpenAI constraint [9]).

**Why.** Anything that changes behavior must live in `prompts/` so the PR
gate evaluates it. Prompt-versioning practice recommends versioning the full
runtime contract — model, temperature, max tokens, response format — not only
the text: "Many teams version prompt text but forget model settings" [10].

## 1.3 Prompt versioning

**Decision.**
- One folder per prompt: `prompts/classifier/`, `prompts/judge/`.
- Immutable version files `vN.yaml`; a single pointer file
  `prompts/active.yaml` (`classifier: v2`, `judge: v1`).
- A CI check fails if a published version is edited; every run records
  `version_id` + sha256 of the file; the PR comment and report show a
  generated diff between baseline and candidate versions; the loader checks
  `version_id` matches the file name.

**Why.** Market tools use immutable numbered versions plus release labels:
PromptLayer ("Do not edit it in place. Create a new version for every
meaningful change"; labels point to immutable versions) [10]; Langfuse
(versions + `production` / `latest` labels) [11]. `active.yaml` plays the
role of the `production` label while keeping prompts in git for the PR gate.

## 1.4 Few-shot examples vs golden set

**Decision.**
- A separate pool of examples that never comes from a golden edition;
  drafted by Claude, approved by Luis in the prompt's PR.
- 7 static examples, one per category, typical `easy` cases; boundary cases
  stay in the golden set to test the tie-break rules.
- Enforced automatically with the duplicate-detection layers of decision 2.6
  (exact, `rapidfuzz.token_sort_ratio`, embeddings).

**Why.**
- Separating examples from the evaluation sample is standard practice ("to
  avoid overlap"); a minimal increase in context gives most of the gain [12].
- Stratified per-class selection beats random; static examples are cheaper
  and keep the prompt identical across calls [13].
- Few-shot helps more than reasoning, especially for smaller models [5].

**Future experiments:** more examples per category; dynamic (retrieved)
examples.

## 1.5 `LLMClient` port

**Decision.**
- One async operation `complete(LLMRequest) -> LLMResult`, generic over the
  output schema.
- `LLMRequest`: model, instructions, few-shot examples, user input, output
  schema, generation parameters.
- `LLMResult`: `parsed`, `raw_text`, `status` (completed / incomplete /
  refusal / error), `served_model`, `usage` (input, cached input, output,
  reasoning tokens), `latency_ms`, `provider_request_id`.
- Cost computed by our code from a versioned `config/pricing.yaml` (CI has no
  Langfuse); the same number goes to the local Langfuse.
- Judge calls go through the same port (DeepEval custom model).
- The response cache is a `CachingLLMClient` adapter wrapping the real client.

**Why.** Observability platforms record the same set per call (model, input,
output, tokens, cost, latency) [14]; `served_model` detects silent alias
changes; `status` separates "the call worked" from "the answer is usable".

## 1.6 Failure handling

**Decision.**

| Type | Examples | Handling |
|---|---|---|
| Infrastructure | Connection, 408/409/429/5xx, timeout | OpenAI SDK retries (exponential backoff with jitter, honors `Retry-After`), `max_retries=4`, 60 s timeout; if exhausted → case `error`, not a classifier miss |
| Configuration | 400 / 401 / 404 | Abort the whole run immediately |
| Model outcome | Refusal, `incomplete` (`max_output_tokens`), invalid output | Not retried; counts as a category miss; status reported separately |

- Run validity: more than 2 % of cases (3 of 140) ending in infrastructure
  error → run **inconclusive** (no verdict, never a baseline, distinct
  message). Below that, errored cases leave both sides of the comparison.
- Judge: same rules; a failed judge call gives a missing score (not zero) and
  counts toward the limit; DeepEval configured not to halt the run.
- The cache stores only `completed` calls, so re-running an inconclusive run
  only spends calls on failed cases.

**Why.**
- The OpenAI SDK retries connection errors, 408, 409, 429 and 5xx with
  exponential backoff and jitter (default 2 retries) and honors
  `Retry-After` [15]; Promptfoo retries transient errors and never permanent
  ones [16].
- Inspect AI separates errored samples from incorrect ones, fails the eval
  above a configurable error count or proportion (`fail_on_error`), scores
  refusals as answers by default, and warns that retrying failed samples can
  shift the distribution [17].
- DeepEval halts the run on a metric error unless `ignore_errors` is set [18];
  LangSmith and Inspect re-run only failed examples [17][19].
- With `max_output_tokens` reached, the Responses API returns
  `status="incomplete"` and the output may be empty [20].

## References

1. Tam et al., *Let Me Speak Freely?* (EMNLP 2024 Industry) — https://arxiv.org/abs/2408.02442 ; https://aclanthology.org/2024.emnlp-industry.91/
2. Weaviate podcast with Zhi Rui Tam (summary, May 2026) — https://neatguycoding.com/posts/2026-05-18-weaviate-podcast-let-me-speak-freely-with-zhi-rui-tam-weaviate-podcast-108/
3. Weaviate podcast with Will Kurt and Cameron Pfiffer, dottxt (summary) — https://neatguycoding-github-io.pages.dev/posts/2026-05-18-weaviate-podcast-structured-outputs-with-will-kurt-and-cameron-pfiffer-weaviate-podcast-1/
4. Sprague et al., *To CoT or not to CoT?* (ICLR 2025) — https://arxiv.org/abs/2409.12183
5. Guo et al., *TextReasoningBench* (arXiv 2603.19558) — https://arxiv.org/html/2603.19558v1
6. *Reasoning or Overthinking: Evaluating LLMs on Financial Sentiment Analysis* (arXiv 2506.04574) — https://arxiv.org/html/2506.04574v1
7. *Rethinking Verbalized Confidence for LLM-as-a-Judge* (arXiv 2609.10996) — https://arxiv.org/html/2609.10996v1
8. Microsoft — Azure OpenAI structured outputs (key ordering) — https://learn.microsoft.com/en-au/azure/ai-services/openai/how-to/structured-outputs
9. OpenAI — Using GPT-6 — https://developers.openai.com/api/docs/guides/latest-model
10. PromptLayer — How to version prompts in production — https://blog.promptlayer.com/how-to-version-prompts-in-production/
11. Langfuse — Prompt management — https://Langfuse.com/docs/prompts/get-started
12. *Navigating the Prompt Space* (arXiv 2603.25422) — https://arxiv.org/html/2603.25422v1
13. Zhukov — Few-shot techniques for text classification using LLMs (2026) — https://vzhukov.dev/posts/2026/few-shot-techniques-for-text-classification-using-llms
14. Inference.net — Langfuse vs LangSmith (2026) — https://inference.net/content/langfuse-vs-langsmith
15. openai-python — Retries — https://www.mintlify.com/openai/openai-python/concepts/retries
16. Promptfoo — Rate limits — https://www.promptfoo.dev/docs/configuration/rate-limits/
17. Inspect AI — Handling errors — https://inspect.aisi.org.uk/handling-errors.html
18. DeepEval — Evaluation flags and configs — https://deepeval.com/docs/evaluation-flags-and-configs
19. LangSmith — Evaluate with retry — https://docs.langchain.com/langsmith/evaluate-with-retry
20. OpenAI Community — Responses API incomplete by `max_output_tokens` — https://community.openai.com/t/responses-api-empty-output-text-no-message-item-when-status-incomplete-due-to-max-output-tokens-reasoning-only-output/1373609
