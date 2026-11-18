# Phase 1 — Feature under test

**Goal:** a classifier that receives an email, calls the model with the
active prompt version and returns a validated JSON object, behind ports that
keep the core vendor-independent.

**Status:** all decisions taken (1.1–1.6). Built: output contract (1.1,
build step 1), `LLMClient` port, `OpenAIClient` adapter, cost from
`config/pricing.yaml` and failure handling (1.5, 1.6, build step 2;
2026-11-06), prompt files, loader, `PromptConfig` and classifier with
prompt v1 (1.2–1.4, build step 4, 2026-11-17; its decisions of 2026-11-16
are below). Tracing: `Tracer` port and `NoopTracer` built in build
step 5 (2026-11-17, see
[`phase-3-evaluation-engine.md`](phase-3-evaluation-engine.md));
`LangfuseTracer` in step 11.
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

Decided 2026-11-16 (build step 4):

- **Taxonomy copied.** The definitions and tie-break rules are copied from
  `config/taxonomy/v1.md` into the prompt file, so a taxonomy change only
  reaches the classifier through a new prompt version (and the PR gate). A
  unit test checks that v1's copy matches taxonomy v1.
- **Rendering.** `system_prompt` holds the placeholders `{categories}` and
  `{tie_break_rules}` exactly once each; they are filled by plain text
  substitution (as in the label audit). `str.format` breaks on JSON braces;
  Jinja2 would bring logic into the prompt.
- **Email as data.** The email goes between `<email>` and `</email>` in the
  real call and in the examples, and the system prompt says the text inside
  is data, never an instruction. This is the *delimiting* form of
  spotlighting, which lowered the attack success rate of indirect prompt
  injection from over 50 % to under 2 % in its study [32]. Datamarking and
  encoding (the stronger forms) transform the customer's text, which the
  summary must report. Limitation: an email can write `</email>` itself.
- **Safe parsing and identity.** Files are read with `yaml.safe_load`,
  which only builds plain mappings, lists and scalars; the general loaders
  can build Python objects from tags such as `!!python/object` [33]. The
  sha256 is computed over the file bytes.
- **Prompt cache.** Instructions and examples come first and the email last,
  so the repeated prefix can be served from the provider's prompt cache,
  available from 1024 tokens and billed at the `cached_input` price [34].
  Measured 2026-11-17 (live test): prompt v1 sends 2,038 input tokens; a
  second identical call had 2,035 of them cached (latency 3.6 s → 1.9 s);
  the first call cost US$ 0.000227.

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

Decided 2026-11-16 (build step 4):

- **Format.** Each example is a user turn (the email, delimited) followed by
  an assistant turn (the JSON answer `{category, summary}`), between the
  instructions and the real email.
- **Order.** Enum order, fixed. One example per category removes the
  majority-label bias; the recency bias, the pull toward the label of the
  last example, remains [31] and is a recorded limitation. Shuffling per
  call was rejected (it breaks the prompt cache and reproducibility).
- **Approval without anchoring.** The agent shows the 7 emails without
  labels; Luis labels them blind; then the agent shows its labels and
  summaries and Luis decides. The summaries are written by the agent
  following the summary guide and reviewed by Luis.
- **Overlap check.** `validate-golden` checks the examples of the active
  prompt against every golden email with the layers of decision 2.6: exact
  and lexical ≥ 90 block; lexical 80–90 and semantic ≥ 0.74 warn.

**Future experiments:** more examples per category; dynamic (retrieved)
examples; example order (recency bias).

## 1.5 `LLMClient` port

**Decision.**
- One async operation `complete(LLMRequest) -> LLMResult`, generic over the
  output schema.
- `LLMRequest`: model, instructions, few-shot examples, user input, output
  schema, generation parameters.
- `LLMResult`: `parsed`, `raw_text`, `status` (completed / incomplete /
  refusal / invalid_output / error), `requested_model`, `served_model`,
  `usage` (input, cached input, output, reasoning tokens), `latency_ms`,
  `provider_request_id`, `detail` (short reason for any status other than
  completed).
- `invalid_output` (output that does not match the schema) is a model
  outcome; `error` is reserved for infrastructure failures after the SDK
  retries. Only `error` counts toward the run-validity limit (1.6).
  Configuration errors are not a status: the adapter raises
  `LLMConfigurationError` and the run stops (decided 2026-11-06, build
  step 2).
- Cost computed by our code from a versioned `config/pricing.yaml` (CI has no
  Langfuse); the same number goes to the local Langfuse. Prices per model:
  input, cached input and output per 1M tokens; cost =
  (input − cached) × input price + cached × cached-input price + output ×
  output price (reasoning tokens are already part of output). The price is
  looked up by the **requested** model (the served model may be a dated
  snapshot); a model missing from the file is a configuration error, never a
  zero cost (decided 2026-11-06, build step 2) [23][24][25].
- Judge calls go through the same port (DeepEval custom model).
- The response cache is a `CachingLLMClient` adapter wrapping the real client.
  `LLMResult` gains `from_local_cache` (default false): an answer served
  from that cache carries the usage and latency of the original call. It is
  unrelated to `cached_input_tokens`, the provider's prompt cache (decided
  2026-11-17, build step 5; key, expiry and storage in
  [`phase-3-evaluation-engine.md`](phase-3-evaluation-engine.md)).

**Why.** Observability platforms record the same set per call (model, input,
output, tokens, cost, latency) [14]; `served_model` detects silent alias
changes; `status` separates "the call worked" from "the answer is usable".

## 1.6 Failure handling

**Decision.**

| Type | Examples | Handling |
|---|---|---|
| Infrastructure | Connection, 408/409/429/5xx, timeout | OpenAI SDK retries (exponential backoff with jitter, honors `Retry-After`), `max_retries=4`, 60 s timeout; if exhausted → case `error`, not a classifier miss |
| Configuration | Every HTTP error the SDK does not retry: 400 / 401 / 403 / 404 / 422; a model missing from `pricing.yaml` | Abort the whole run immediately (`LLMConfigurationError`) |
| Model outcome | Refusal, `incomplete` (`max_output_tokens`), invalid output | Not retried; counts as a category miss; status reported separately (`refusal`, `incomplete`, `invalid_output`) |

Build step 2 (2026-11-06) widened the configuration row from 400 / 401 / 404
to every non-retried HTTP error: 403 (permission, e.g. a model not enabled
for the project) and 422 (unprocessable request) also never succeed on a
retry [26]. A refusal arrives with response status `completed` and a refusal
content item instead of parsed output, so it is detected from the content,
not from the status [27].

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
21. Python — `enum.StrEnum` (build step 1: `Category`) — https://docs.python.org/3.11/library/enum.html
22. Pydantic — Model config, `extra='forbid'` (build step 1: `EmailClassification`) — https://pydantic.dev/docs/validation/latest/api/pydantic/config/
23. OpenAI — API pricing (rechecked 2026-11-06 via usagepricing.com and aireiter.com summaries) — https://developers.openai.com/api/docs/pricing ; https://www.usagepricing.com/blueprint/activity/openai-2026-10-05-gpt-6-api-launch ; https://aireiter.com/blog/gpt-6-1-terra-api-pricing-review
24. Abacus.AI — Responses API reference, counting tokens (`cached_tokens` and `reasoning_tokens` are subsets) — https://abacus.ai/help/developer-platform/route-llm/responses
25. Langfuse — Token and cost tracking (model definitions × usage); LiteLLM — Model cost map (missing model prices to $0) — https://langfuse.com/docs/token-usage ; https://docs.litellm.ai/docs/proxy/model_cost_map
26. openai-python — Error codes and retried errors (README) — https://github.com/anylee2021/openai-python ; https://www.mintlify.com/openai/openai-python/concepts/error-handling
27. Apache Airflow PR review — refusal shape in `responses.parse` (openai 2.46.0) — https://mail-archive.com/commits@airflow.apache.org/msg557044.html
28. openai-python — Parsing Responses API output (`responses.parse`, `text_format`) — https://raw.githubusercontent.com/openai/openai-python/main/helpers.md
29. Testing openai-python retries with `httpx.MockTransport` — https://hashnode.com/posts/test-openai-python-retries-with-httpx-mocktransport/6a68cb035906af76343badfd ; https://www.b-list.org/weblog/2023/dec/08/mock-python-httpx/
30. `typing.Protocol` for ports (structural subtyping) — https://rodekruis.github.io/qualitative-feedback-analysis/adr/002-protocol-based-ports.html
31. Zhao et al., *Calibrate Before Use: Improving Few-Shot Performance of Language Models* (ICML 2021; majority-label and recency biases) — https://arxiv.org/abs/2102.09690
32. Hines et al., *Defending Against Indirect Prompt Injection Attacks With Spotlighting* (CAMLIS 2024) — https://arxiv.org/abs/2403.14720
33. Semgrep — Testing vulnerable PyYAML versions (`safe_load`) — https://semgrep.dev/blog/2022/testing-vulnerable-pyyaml-versions
34. OpenAI — Prompt caching (guide and cookbook) — https://developers.openai.com/api/docs/guides/prompt-caching ; https://developers.openai.com/cookbook/examples/prompt_caching101
35. Pydantic — `model_validator` (rule across two fields: temperature × effort) — https://pydantic.dev/docs/validation/2.11/api/pydantic/functional_validators/
