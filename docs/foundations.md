# Foundations — cross-cutting decisions

Decisions that apply to every phase: scope, domain, taxonomy, models, tools,
architecture, languages and naming. Phase-specific decisions live in
[`phases/`](phases/). The dated log of every decision is
[`planning.md` §12](planning.md#12-decisions); this document explains each one
with its rationale and sources (numbers in brackets point to the
References section at the end).

## F1. What the project is

- **Center:** a trustworthy measuring instrument for a non-deterministic LLM
  feature (golden set, scoring, judge, signal vs noise). CI is how the
  instrument is enforced, not the point of the project.
- **One trigger: the PR.** Every PR that changes a prompt runs the gate
  (blocks the merge on critical regressions). No scheduled runs: the feature
  is never in production, so the gate is an extra validation layer at PR
  time (decided 2026-11-04).
- **Nothing is deployed or published.** Everything runs locally or on GitHub
  Actions runners. The Telegram bot only sends messages, so it needs no
  server. The feature never goes to production; every evaluation uses the
  golden set, not live traffic.
- **No time planning.** Phases are described by sub-steps, decisions and
  justifications, and executed one at a time.

## F2. The feature under test

- Customer support email classifier for a **fictional Brazilian
  marketplace**. Only the **buyer** writes (sellers are out of scope; a
  misrouted seller email is an `out_of_scope` case).
- Output: one of 7 categories + a one-sentence summary.
- **Prompt-only:** no RAG, no fine-tuning. Behavior changes only through the
  prompt text, the few-shot examples, and the model + generation parameters.
- Why an LLM and not a fine-tuned encoder: fine-tuned encoders match or beat
  prompted LLMs on fixed-label classification at a fraction of the cost, but
  only with tens of thousands of labeled examples; prompting fits when labeled
  data is scarce and labels are still being designed — our case [1].

## F3. Category taxonomy

Seven categories, each a real destination team, mutually exclusive and
collectively exhaustive (`general` is the catch-all). Definitions, master
rule and tie-break rules: [`planning.md` §4](planning.md#category-taxonomy).

- 4 categories were too easy (little room to detect regressions); 8 forced a
  tone-based `complaint` category that breaks mutual exclusivity; 6 were
  chosen, then `technical` was added because app/site failures go to a
  separate team in a marketplace.

## F4. Languages

- Emails, expected summaries, notes and **prompts** (classifier and judge)
  are in **Portuguese** — this is a Brazilian product. ~10 % English or mixed
  emails are an edge case; summaries are always Portuguese.
- Code, identifiers, JSON keys, label values, logs and all documentation are
  in **English**.

## F5. Models and API

| Role | Model | Why |
|---|---|---|
| Feature | `gpt-6-luna`, `reasoning_effort: none`, `temperature: 0` | Built for focused high-volume tasks; cheapest current model; supports `none` effort so `temperature` is allowed [2][3][4] |
| Judge | `gpt-6.1-terra`, `reasoning_effort: none`, `temperature: 0` | Stronger than the feature (avoids grading itself); supports `none` effort [2][3] |
| API | OpenAI Responses API with structured outputs | Recommended for GPT-6; isolated in the `OpenAIClient` adapter [3] |

- Single provider (OpenAI). The optional cross-family judge was dropped;
  Gemini 3 also recommends keeping `temperature` at 1.0 [5].
- `gpt-5.4-nano` is deprecated (shutdown 2027-04-01) [6]; `gpt-5.4-mini` is a
  previous generation and costs 7.5× more on input [2].
- `gpt-6-luna` is published as an alias only, so every run records the model
  ID actually served.
- **Model IDs are configuration, not secrets:** they live in versioned files
  (prompt YAML), never scattered in code. Environment variables hold secrets
  only (portfolio `CLAUDE.md`).

### Generation parameters (terminology)

`temperature`, `top_p`, output-token limit and reasoning effort are
**generation parameters** — settings of how each token is sampled from the
trained model. They are not model parameters (weights) nor training
hyperparameters. `temperature` divides the logits before the softmax; it
changes how often a non-top token is sampled, never what the model knows.
Provider constraints checked on 2026-11-03: OpenAI accepts `temperature` /
`top_p` only with `reasoning.effort = none` [3]; Gemini 3 recommends the
default 1.0 [5]; Anthropic rejects non-default sampling values on its newest
models [7].

## F6. Market tools

| Tool | Role here | Why |
|---|---|---|
| **DeepEval** (Apache 2.0) | Summary judge (G-Eval) | Python, runs locally and in CI with no account; one of the two frameworks that survived as a CI gate in an 8-month practitioner test [8][9] |
| **Langfuse** (MIT core) | Local observability: golden edition as dataset, prompt versions, traces, scores, experiments | Open source, runs locally with Docker Compose; GitHub runners cannot reach `localhost`, so CI uses a no-op tracer [10][11][12] |
| **scikit-learn** | Classification metrics | Industry standard `classification_report` (Phase 3) |
| **OpenAI Python SDK** | Retries with backoff | Built-in, honors `Retry-After` (Phase 1) |
| **Telegram Bot API** | Alerts | Free, official, plain HTTPS; Slack's free plan works but the alert must go where it is read; unofficial WhatsApp libraries break ToS and need a QR-code session that does not fit CI [13] |

Not adopted: **Promptfoo** (Node-based, own config format, its GitHub Action
evaluates only the current checkout — no base vs candidate comparison) [14];
**Langfuse prompt management as source of truth** (prompts would leave git
and changes would bypass the PR gate) [11]; **Dify** (builds LLM apps, does not
evaluate them; prompts would live in its database); **Spring Boot / Next.js
dashboard** (a layer outside the CI-gate core).

Built here because no tool covers it: per-case comparison against a stored
baseline, signal vs noise, the PR gate and the Telegram alert.

## F7. Architecture

Ports and adapters: the core never imports a vendor SDK. Four ports —
`LLMClient`, `Notifier`, `RunRepository`, `Tracer` — with adapters chosen in
one composition root. Diagrams, flows and layout:
[`planning.md` §6](planning.md#6-architecture).

- Git is the source of truth for prompts and golden editions; Langfuse only
  receives one-way copies and is never edited directly.
- Secrets in CI: `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
  Langfuse keys live only in the local `.env`.

## F8. Naming conventions

| Thing | File | Referred to as |
|---|---|---|
| Prompt version | `prompts/classifier/v3.yaml`, `prompts/judge/v1.yaml` | "classifier prompt v3", "judge prompt v1" |
| Golden set edition | `golden/edition-1.json` | "golden edition 1" |

`active.yaml` points to the **active** version; a version under review is a
**candidate**; the **baseline** is the last approved run on `main`.

## References

1. Valdes Gonzalez, *Cost-Aware Model Selection for Text Classification* (arXiv 2602.06370) — https://arxiv.org/html/2602.06370v1
2. OpenAI — API pricing — https://developers.openai.com/docs/pricing
3. OpenAI — Using GPT-6 (latest-model guide) — https://developers.openai.com/api/docs/guides/latest-model
4. OpenAI — GPT-6 Luna model page — https://developers.openai.com/api/docs/models/gpt-6-luna
5. Google Cloud — Gemini 3 prompting guide — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/gemini-3-prompting-guide
6. OpenAI — Deprecations — https://developers.openai.com/api/docs/deprecations
7. Kingy AI — Anthropic deprecates non-default sampling controls — https://kingy.ai/ai-launch-tracker/anthropic-deprecates-non-default-sampling-controls-on-newer-claude-models/ ; Developers Digest — Claude API 2026-10-21 migration — https://developersdigest.tech/blog/claude-api-version-2026-10-21-sdk-migration
8. DeepEval — FAQ — https://deepeval.com/docs/faq ; Unit testing in CI/CD — https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd
9. *We gated CI on six open-source LLM eval frameworks* — https://dev.to/ethanwritesai/we-gated-ci-on-six-open-source-llm-eval-frameworks-only-two-survived-the-merge-queue-5elf
10. Langfuse — Self-host locally — https://python-sdk-v2.docs-snapshot.langfuse.com/self-hosting/local
11. Langfuse — Prompt CI/CD — https://langfuse.com/resources/engineering/prompt-cicd ; GitHub integration — https://langfuse.com/docs/prompt-management/features/github-integration
12. Inference.net — Langfuse vs LangSmith (2026) — https://inference.net/content/langfuse-vs-langsmith
13. Dupple — Is Slack free in 2026? — https://dupple.com/learn/is-slack-free
14. Promptfoo GitHub Action — https://github.com/promptfoo/promptfoo-action
