# Model Regression Detection — Agent Guide

Entry point for any AI agent helping Luis on this project. The portfolio rules
in [`../CLAUDE.md`](../CLAUDE.md) also apply.

## Current state (updated 2026-11-06)

- **Decisions closed:** foundations, Phase 1 (1.1–1.6), Phase 2 (2.1–2.6),
  Phase 3 (3.1–3.6), Phase 4 (4.1–4.2), Phase 5 (5.1–5.3), Phase 6
  (6.1–6.3). **All planning decisions are closed.** See `docs/planning.md`
  §12. The demo video outline (6.2) is revisited with Luis before recording.
- **Implementation plan approved (2026-11-05):** 18 build steps in
  [`docs/implementation-plan.md`](docs/implementation-plan.md), with the
  working rules for each step and a status table.
- **Step 1 done (2026-11-06)** on branch
  `step-1-models-and-golden-validation`: public GitHub repository;
  `Category` and `EmailClassification` (`feature/models.py`); golden file
  schema (`golden/schema.py`); exact and lexical duplicate detection
  (`golden/dedup.py`); offline validation (`golden/validation.py`) and the
  `uv run validate-golden` command (`golden/cli.py`); crafted fixture of
  text pairs (`tests/test_dedup.py`). `uv run pytest` passes (41 tests) and
  the draft has 0 flags.
- **Step 2 done (2026-11-06)** on branch `step-2-llm-client`: `LLMClient`
  port (`ports/llm.py`), `OpenAIClient` adapter
  (`adapters/openai_client.py`), cost from `config/pricing.yaml`
  (`pricing.py`), `live` pytest marker. Decisions of the step in
  `docs/planning.md` §12 (`invalid_output` status, wider configuration
  errors, cached-input price, `live` marker, own parsing instead of
  `responses.parse`). `uv run pytest`: 67 passed, 1 deselected; the real
  call (`uv run --env-file .env pytest -m live -s`) passed.
- **Next step: 3** (embeddings, semantic duplicates, LLM label audit). Not
  started; nothing is built until Luis asks for the step. One branch and one
  PR per step, merged by Luis. Code and test files are handed to Luis in
  the chat (all files of the step at once, on his request of 2026-11-07).
- **Code that exists:** domain models, golden schema, duplicate detection
  (exact and lexical), validation, LLM port, OpenAI adapter and cost
  computation. No classifier or evaluation code yet.
- **Golden edition 1:** 140 cases drafted and reviewed (2026-11-04); review
  items R1–R5 resolved
  ([`golden/drafts/review-notes.md`](golden/drafts/review-notes.md)). The
  validation script confirms every exact coverage target and finds no exact
  or lexical duplicates (2026-11-06). Still draft: semantic duplicates and
  label audit (step 3), few-shot overlap (step 4), intra-annotator check and
  freeze (step 10).
- **Progress tracking:** steps cross phases, so a §7 box in
  `docs/planning.md` is ticked only when every part of it is built; a box a
  step covers only in part stays unticked with a dated status line under it.
  The status table in `docs/implementation-plan.md` is the per-step record.
- Decisions are made one sub-step at a time: research, explain the terms,
  recommend, wait for Luis's approval, then record (see the last section).

## Read order

1. [`docs/planning.md`](docs/planning.md): the source of truth. Read §4 Data,
   §6 Architecture, §7 Build plan (the checkboxes show progress) and §12
   Decisions.
2. [`docs/implementation-plan.md`](docs/implementation-plan.md): the
   approved build order (steps 1–18), how each step is run, open items and
   status.
3. The phase document for the phase being worked on, in
   [`docs/phases/`](docs/phases/).
4. The guide for the task at hand, in [`docs/guides/`](docs/guides/) (see the
   routing table below).
5. [`docs/foundations.md`](docs/foundations.md) when the question is about
   concepts, models, tools or naming.

## Hard rules

- **Luis types the golden content.** Agents may include one example email in
  each brief for inspiration; Luis types his own email, writes the expected
  summary and decides the labels. Agents never put their example into the
  dataset.
- **No anchoring.** When Luis has to judge something (a label, a summary),
  ask for his answer before showing any model output or agent opinion.
- **Never edit a published prompt version** (`prompts/<feature>/vN.yaml`).
  Create a new version instead.
- **No secrets in files.** Secrets go in `.env` (gitignored) and GitHub
  Secrets. Model IDs are not secrets; they live in versioned config.
- **Language.** Files in English. Conversation with Luis in Portuguese.
  Golden emails, summaries and prompts are in Portuguese; label values are in
  English.
- **No schedules or time estimates.** Describe phases and sub-steps and
  justify decisions.
- **Do not advance without being asked.** At most, offer next-step options.
- **Research before recommending.** Check market tools (what they do, whether
  they run locally) before proposing to build something. Cite sources.
- **Explain before deciding.** This is a learning project: explain the
  problem, the concepts and every metric or acronym before asking Luis to
  decide.
- **Luis types the code.** Agents never create code, test or config files
  unless Luis asks: they prepare each file's content, Luis types or copies
  it, and the agent explains the code. Documentation files are written by
  the agent (delegated by Luis on 2026-11-05). The agent may test code in a
  scratch copy under `/tmp` (never in the repository) to verify it and to
  compare it with what Luis typed, never as a copy-paste shortcut.
- **Before every build step:** explain it in Portuguese (what it is in
  practice; "with it done we can X, which makes Y possible"; technologies;
  every file and why it exists) and survey the references behind that
  step's decisions — that step only, never all steps at once.
- **Always explain and ask.** Any conflict between decisions or open
  question is explained with the evidence and Luis decides.
- **Stay on this project.** No tangents about other projects or stacks.
- **PR-only gate.** The feature is never in production and there are no
  scheduled runs; the evaluation is an extra validation layer when a PR is
  opened. Do not propose schedules, production monitoring or deploys.

## Naming

- Prompt versions: `prompts/classifier/v1.yaml`, `v2.yaml`… ("prompt v2").
- Golden set editions: `golden/edition-1.json`… ("edition 1"). Never call an
  edition "v1".
- Golden case IDs: `<category>-<NNN>` (e.g. `delivery-007`), never reused.

Full rules: [`docs/planning.md` §4 Naming conventions](docs/planning.md#naming-conventions).

## Routing table for manual tasks

| Luis wants to… | Use |
|---|---|
| Write golden cases | [`docs/guides/golden-case-authoring.md`](docs/guides/golden-case-authoring.md) |
| Resolve validation flags (duplicates, label conflicts, gaps) | [`docs/guides/validation-flags.md`](docs/guides/validation-flags.md) |
| Resolve LLM label audit flags | [`docs/guides/label-audit.md`](docs/guides/label-audit.md) |
| Do the blind re-labeling check | [`docs/guides/intra-annotator-check.md`](docs/guides/intra-annotator-check.md) |
| Label summaries to calibrate the judge | [`docs/guides/judge-calibration.md`](docs/guides/judge-calibration.md) |
| Review prompt v1 or create a new prompt version | [`docs/guides/prompt-change.md`](docs/guides/prompt-change.md) |
| Set up OpenAI, Langfuse, Telegram, GitHub secrets | [`docs/guides/initial-setup.md`](docs/guides/initial-setup.md) |
| Check whether a summary is correct | [`docs/summary-guide.md`](docs/summary-guide.md) |

Ready-to-paste agent prompts for the long manual tasks:
[`docs/agent-prompts/golden-authoring-agent.md`](docs/agent-prompts/golden-authoring-agent.md)
(golden cases),
[`docs/agent-prompts/golden-review-agent.md`](docs/agent-prompts/golden-review-agent.md)
(resolving golden review items),
[`docs/agent-prompts/decision-session.md`](docs/agent-prompts/decision-session.md)
(closing the planning decisions; all closed on 2026-11-04, kept as history),
[`docs/agent-prompts/implementation-plan-session.md`](docs/agent-prompts/implementation-plan-session.md)
(making the build order with Luis and building step by step) and
[`docs/agent-prompts/judge-calibration-agent.md`](docs/agent-prompts/judge-calibration-agent.md)
(labeling the 100 calibration summaries, after the code generates them).

## When a decision is made or changed

Update all of these together:

1. [`docs/planning.md`](docs/planning.md): the affected section, the phase
   checklist in §7 and a dated entry in §12 Decisions (a change says what it
   replaces and why).
2. The phase document in [`docs/phases/`](docs/phases/): the sub-step's
   decision, its rationale, and any new sources in its References section
   (title and link).
3. Any guide in [`docs/guides/`](docs/guides/) whose procedure changes.
4. [`docs/implementation-plan.md`](docs/implementation-plan.md) if the build
   order, an open item or a step's status changes.
5. This file and [`README.md`](README.md) if a document is added, renamed or
   removed.
