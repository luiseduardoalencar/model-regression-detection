# Guide — Reviewing and changing a prompt

**Used in:** Phase 1 (review of classifier prompt v1 and its 7 few-shot
examples) and every later prompt change (decisions 1.2–1.4).

## Rules that never change

- Published versions are **immutable**: never edit `vN.yaml` after it is on
  `main`; create `vN+1.yaml` (a CI check enforces this).
- The active version is set only in `prompts/active.yaml`.
- Prompts are edited in git only — never in the Langfuse UI.
- Every behavior change (text, examples, model, generation parameters) is a
  new version, because the PR gate only evaluates what is in `prompts/`.
- `temperature` only with `reasoning_effort: none`.
- Category definitions and tie-break rules must match the taxonomy in
  [`../planning.md` §4](../planning.md#category-taxonomy); summary
  instructions must match [`../summary-guide.md`](../summary-guide.md).

## Review of classifier prompt v1 (once)

The agent drafts v1 from the approved taxonomy and the summary guide; Luis
reviews with this checklist:

- [ ] The 7 categories and their definitions match the taxonomy.
- [ ] All tie-break rules and the master rule are present and unambiguous.
- [ ] Summary instructions follow the 10 rules of the summary guide.
- [ ] 7 few-shot examples: one per category, typical `easy` cases, written in
      Portuguese, approved by Luis, and **not similar to any golden case**
      (the overlap check must pass).
- [ ] Generation parameters: `reasoning_effort: none`, `temperature: 0`,
      `max_output_tokens: 200`.
- [ ] `change_note` explains the version in one line.

## Creating a new version

1. Copy the active version to `prompts/classifier/vN+1.yaml`; set
   `version_id`, `created_at` and a `change_note` (what changes and why).
2. Make the change.
3. Point `prompts/active.yaml` to the new version.
4. Run the evaluation locally; read the report and the Langfuse experiment
   next to the baseline's; iterate until satisfied.
5. Open a PR. The CI job runs the active prompt on `main` (baseline) and the
   candidate side by side and posts the result.
6. If the gate blocks: read the regressed cases, fix the candidate (new
   commit), repeat. If it passes: merge; the new version becomes the active
   prompt and therefore the baseline of the next PR.

Rolling back = pointing `active.yaml` to an older version in a PR.

## Proof scenarios (Phase 6, decision 6.1)

Same steps as "Creating a new version", with three additions:

1. **Before running anything** (locally or in CI), write the expected verdict
   of the scenario in `docs/proof-scenarios.md`.
2. Name things so the scenario is identifiable: branch
   `scenario/<n>-<name>`, `change_note` starting with "Scenario <n>:", PR
   title `[Scenario <n>] …`. Version numbers are never reused, even in
   closed PRs.
3. After the gate runs, record the observed verdict, the PR link and the
   cost. Scenarios 1–3 are closed without merging; scenario 4 (improvement)
   is merged last. Never change a threshold to make a scenario pass.

## References

1. Langfuse — Prompt CI/CD — https://langfuse.com/resources/engineering/prompt-cicd
2. Langfuse — GitHub integration for prompts — https://langfuse.com/docs/prompt-management/features/github-integration
3. PromptLayer — How to version prompts in production — https://blog.promptlayer.com/how-to-version-prompts-in-production/
4. OpenAI — Using GPT-6 (`reasoning_effort` and sampling parameters) — https://developers.openai.com/api/docs/guides/latest-model
5. vzhukov — Few-shot techniques for text classification using LLMs — https://vzhukov.dev/posts/2026/few-shot-techniques-for-text-classification-using-llms
