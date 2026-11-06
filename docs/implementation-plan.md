# Implementation plan (build order)

Approved by Luis on 2026-11-05. It turns the closed decisions of
[`planning.md`](planning.md) into an ordered list of build steps. Each step
ends in something runnable or testable and maps to the
[§7 checklist](planning.md#7-build-plan). No dates or time estimates.

**Naming.** The 18 items below are **steps**. The planning document's
"Phases 1–6" are a different grouping; in the last column, F1–F6 refer to
the §7 checklist of each phase.

## How each step is run

Working rules set by Luis on 2026-11-05:

1. **Detail first.** Before a step starts, the agent explains it in
   Portuguese: what it is in practice, what it enables ("with this step done
   we can X, which makes Y possible"), the technologies involved, every file
   to be created and why each one exists, and every new term.
2. **References per step.** Before a step starts, the agent surveys the
   references behind that step's decisions — only that step, never all at
   once — and cites real sources. Once Luis approves the step, new sources
   go into the References section of the matching phase document.
3. **Luis types the code.** The agent never creates code, test or config
   files unless Luis asks. It prepares each file's content, Luis types or
   copies it, and the agent explains the code and then reads the file to
   check it. Documentation files (this plan, `CLAUDE.md`, `README.md`,
   `planning.md`, phase documents, guides, checkboxes) are written by the
   agent.
4. **Always explain and ask.** Any conflict between decisions or open
   question is explained to Luis with the evidence, and he decides. Nothing
   is changed silently.
5. **Close and stop.** At the end of a step: tests pass, the §7 boxes are
   ticked, `CLAUDE.md` "Current state" and the status table below are
   updated, and the agent offers the next step without starting it.

## Ordering principles

- **Golden set first.** Freezing edition 1 depends on Luis's manual work
  (validation flags, label audit) and on the interval the intra-annotator
  guide requires after the audit. Starting there lets that work run in
  parallel with the engine code.
- **Core tested offline before real calls.** Runner, scoring, gate and
  report are tested with a fake LLM client, without API cost.
- **No anchoring.** No model output on golden cases is shown to Luis before
  the intra-annotator check (step 10). Until then, real calls use invented
  emails outside the golden set.
- **Dependencies from the documents.** The gate needs the runner and scoring;
  the absolute floor needs the first measured run of classifier prompt v1;
  the proof scenarios need the CI gate, the floor and the noise check.

## Steps

| # | What is built | What exists at the end (how to check) | Luis's manual work (guide) | §7 items |
|---|---|---|---|---|
| 1 | Git repository and public GitHub repository (pushed from the first commit; progress pushed step by step); `Category` enum and `EmailClassification` (1.1); Pydantic schema of the golden file; **offline** validation: unique IDs, enums, coverage matrix (2.1–2.3), exact and lexical duplicates, label conflicts; crafted fixture of text pairs | `uv run validate-golden` lists the flags of the draft; `uv run pytest` passes | Resolve flags (`guides/validation-flags.md`) | F1 output models (part); F2 schema + validation (part); F2 fixture |
| 2 | `LLMClient` port (`LLMRequest` / `LLMResult`); `OpenAIClient` adapter (Responses API, `max_retries=4`, 60 s timeout, status mapping); cost from `config/pricing.yaml` (prices re-checked) | Unit tests with simulated HTTP responses for each failure type; one real call with an invented email | OpenAI key and monthly limit (`guides/initial-setup.md` §1) | F1 port + adapter; F1 pricing and cost; F1 failure handling |
| 3 | Semantic duplicate layer (embeddings, ≥ 0.92 warns); label audit command (`gpt-6.1-terra`, 3 prompt variants) | Full validation; `uv run audit-labels` writes the list of flagged cases | Semantic flags (`guides/validation-flags.md`); audit flags (`guides/label-audit.md`). The interval required before step 10 starts here | F2 validation (complete except few-shot); F2 label audit |
| 4 | `PromptConfig`; YAML loader (enum, temperature × effort rule, `version_id` = file name, sha256); `prompts/active.yaml`; `classify()`; draft of classifier prompt v1 with 7 few-shot examples | `uv run classify "<email>"` returns `{category, summary}`; the loader rejects invalid YAML files; few-shot × golden overlap check passes | Review v1 and approve the 7 few-shot examples (`guides/prompt-change.md`); overlap flags (`guides/validation-flags.md`) | F1 classifier; F1 versioned prompts + loader; F1 `PromptConfig`; F1 few-shot examples |
| 5 | Async runner with a concurrency limit; run validity (infra errors > 2 % → inconclusive); `CachingLLMClient`; `RunRepository` + `SQLiteRunRepository`; `Tracer` port + `NoopTracer` | The full exam runs offline with a fake client; a re-run only spends calls on failed cases | — | F3 runner; F3 run validity (infra); F3 re-run; F3 cache; F3 repository; F1 Tracer (part) |
| 6 | Per-case scoring: category (exact / acceptable / miss), format code checks, latency, tokens, cost; 3.1 metrics (`classification_report`, confusion matrix + "no answer" column, slices with n) | Tests with fabricated results match hand-computed numbers | The "starts with Cliente" × summary rule 9 case (see open items) | F3 multi-dimensional scoring (without summary); F3 classification metrics |
| 7 | Paired comparison by `id`; net drop; gate rules (5 / 7, adversarial invariant, floor, inconclusive); exit codes 0 / 0 / 1 / 2; per-case diff by severity; `config/gate.yaml` (floor empty) | Verdict tests: 7 regressions → `blocked`; 4 → `passed`; adversarial flip → `blocked`; 3 % infra errors → `inconclusive`; cumulative drops crossing the floor → `blocked` | — | F3 baseline (logic); F3 per-case diff; F3 gate rules; F5 `gate.yaml` (part); F6 unit-test scenarios |
| 8 | Summary judge: judge prompt v1 (Portuguese); one DeepEval `GEval` per checklist item; DeepEval → `LLMClient` adapter; `summary_pass` / `summary_score` computed in code; judge failure = missing score | Tests with a fake judge; one real call on a summary outside the golden set | Read judge prompt v1 | F3 summary judge; F3 judge via `LLMClient`; F3 run validity (judge) |
| 9 | HTML report (7 sections, Jinja2 with autoescape); PR comment; `Notifier` port + `ConsoleNotifier` + `TelegramNotifier`; composition root (`config.py`) and the `uv run eval` command | A sample report from fabricated results that Luis opens in the browser; a real Telegram message with the report attached | Create the Telegram bot (`guides/initial-setup.md` §3) | F4, all items |
| 10 | Intra-annotator script (20 cases, fixed seed, Cohen's kappa); freeze command (refuses when a criterion is missing) | `golden/edition-1.json` frozen, header filled in | Blind re-labeling of 20 cases (`guides/intra-annotator-check.md`) | F2 authoring loop (closes); F2 intra-annotator check; F2 freeze |
| 11 | Local Langfuse (`infra/langfuse/` Docker Compose); `LangfuseTracer`; prompt registration (label `active`); one-way copy of dataset `golden-edition-1` | Dataset and classifier prompt v1 visible at `localhost:3000` | Start Langfuse and create keys (`guides/initial-setup.md` §2) | F1 local Langfuse; F1 Tracer (complete); F2 Langfuse dataset; F3 Langfuse experiment |
| 12 | First measured run of classifier prompt v1 on edition 1; "nothing changed" check (3 runs, cache bypassed) → `docs/noise-check/` | v1 report and Langfuse experiment; noise report committed (≈ US$ 3 for the 4 runs) | Read the report; decide the absolute floor value (recorded decision) | F3 "nothing changed" check |
| 13 | Judge calibration: 100 summaries (60 from v1, 40 from a degraded prompt); split 15 / 45 / 40; TPR, TNR, kappa, flip rate | Report in `docs/judge-calibration/`; calibration status shown in the report header | Label 100 summaries (`guides/judge-calibration.md`) | F3 judge calibration |
| 14 | `checks.yml` (unit tests, published-prompt immutability, golden validation, few-shot overlap) | A test PR is green; a PR that edits `v1.yaml` is red | Repository secrets (`guides/initial-setup.md` §4) | F5 `checks.yml` |
| 15 | `eval.yml`: `is_eval_relevant`; baseline (`main`) and candidate in the same job; artifact; PR comment; Telegram; concurrency; fork handling; pinned `setup-uv` | First real gate run: the PR that writes the floor into `gate.yaml` (v1 × v1, expected `passed`); `eval` becomes a required check | Required check on `main` (`guides/initial-setup.md` §4) | F5 `eval.yml`; PR comment; concurrency; fork PRs; `gate.yaml` (complete); required check; no CI history; `is_eval_relevant` tests; CI environment; F3 baseline (CI) |
| 16 | `Dockerfile`; `.dockerignore` (+ unit test); `docker.yml` (build only); onboarding README | `docker build` and `docker run --env-file .env` run the eval | Optional: run with Docker (`guides/initial-setup.md` §5) | F5 Dockerfile; `.dockerignore`; `docker.yml`; README |
| 17 | `docs/proof-scenarios.md` with expected verdicts written **before** any run; PRs v2–v5 (v5 merged last); `docs/sample-report/` | Expected × observed table with PR links and cost | Run the scenario PRs (`guides/prompt-change.md`, "Proof scenarios") | F6 proof scenarios (PRs); F6 `proof-scenarios.md` |
| 18 | `docs/write-up.md`; README links and BASWE credit; pre-publish checklist | Write-up with every number traceable to a repository file | Video outline revisited with Luis; record the video; LinkedIn post | F6 video; write-up; README links; LinkedIn post; pre-publish checklist |

Judge calibration (13) does not block the gate (the judge is always
advisory); it is recommended before step 17 so the reports in the video
show the real calibration status. The observed-difficulty analysis
(decision 2.3) only feeds edition 2 and is outside this plan.

## What each step enables

1. Validate the golden set with one command → flags resolved on the way to
   the freeze; the same command becomes a CI check (14); one shared list of
   categories.
2. Real model calls with measured cost and classified failures → the audit
   (3), the classifier (4) and the judge (8) all go through one port; cost
   per run is reported even in CI.
3. Label errors and repeated scenarios found before the freeze → a model
   "miss" is the model's error, not the answer key's.
4. Any email classified with prompt v1 → there is something to measure;
   everything after compares versions of this prompt.
5. The whole exam runs and repeats without paying twice → scoring and
   comparison; a run broken by an API outage resumes on the missing cases
   only.
6. Statements such as "v1 gets X % right and confuses `delivery` with
   `cancellation`" → the gate and the report.
7. Two runs become one objective, tested verdict → merge blocking in CI
   (15); three proof scenarios proved by unit tests without API cost.
8. Summary quality measured and its drops shown → judge calibration (13)
   and scenario 2 (a summary-only change never blocks).
9. End-to-end run with one command, read in the browser and on the phone →
   the first real run (12) and CI (15) produce the same output.
10. A fixed, trusted answer key → every later number (floor, noise,
    scenarios, write-up) refers to edition 1; model outputs on golden cases
    can be shown without anchoring.
11. Visual investigation of failed cases while developing a prompt → faster
    local iteration; no effect on the gate.
12. A floor based on a real number and proof that the 7-case threshold is
    above natural variation → the gate can be trusted; prerequisite of the
    proof scenarios.
13. Evidence on whether summary warnings deserve trust → the report shows
    "calibrated" or "uncalibrated".
14. PRs with the project rules enforced by machine → `eval.yml`; prompt
    immutability stops depending on discipline.
15. No prompt change merges unmeasured → the proof scenarios (real PRs).
16. Anyone can reproduce the eval without Python or uv → the §11
    deliverable.
17. Evidence that the gate blocks what it should and lets good changes
    through → the video and the write-up with real numbers.
18. The project published in the portfolio; runner, scoring and diff reused
    by the next projects.

## Open items, raised with Luis when the step arrives

None of these changes a recorded decision until Luis approves.

- **Step 1 — approximate coverage targets (decided 2026-11-05).** The
  validator flags only exact targets; approximate ones (~10 % English/mixed
  per case type, difficulty mix per type) are shown as information.
  Edition 1 is kept; the confounding of language with adversarial subtype
  is a recorded limitation (`planning.md` §12,
  `phases/phase-2-golden-dataset.md` 2.1).
- **Step 3 — embeddings.** The `LLMClient` port only has `complete`; how the
  embeddings call is wired, and how the semantic layer behaves in
  `checks.yml` on fork PRs (no secrets).
- **Steps 3 and 13 — support prompts.** The label-audit prompts and the
  degraded calibration prompt live outside `prompts/`, because any change
  there triggers the eval gate.
- **Step 4 — few-shot approval (resolved 2026-11-05).** The GitHub
  repository now exists from step 1, so v1 and its 7 few-shot examples are
  approved in a real PR, as decision 1.4 says.
- **Step 6 — format check vs summary rule 9.** `format_pass` requires the
  summary to start with "Cliente" (3.2), while rule 9 of the summary guide
  makes `out_of_scope` summaries start with "Email de…" / "Vendedor…"
  (`general-008`, `general-015`). To be explained and decided when step 6
  starts.
- **Step 12 — absolute floor value.** Set by Luis after the first measured
  run; recorded as a decision.

## Status

| Step | Status |
|---|---|
| 1 | Detail and references presented (2026-11-05); waiting for Luis's approval before the first file |
| 2–18 | Not started |
