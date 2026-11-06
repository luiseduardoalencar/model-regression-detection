# Phase 6 — Portfolio

**Goal:** prove the system works and tell the story — demonstration
scenarios, a short demo video and a write-up.

**Status:** decisions closed (6.1–6.3, 2026-11-04); the video outline is
revisited with Luis before recording. Not implemented yet.
Implementation checklist: [`planning.md` §7, Phase 6](../planning.md#phase-6--portfolio-polish).

## 6.1 Proof scenarios

**Decision (2026-11-04).** Prove the detector with real gate runs on real PRs
in the public repository, plus unit tests for the rules that real PRs cannot
exercise cheaply. Every scenario changes prompts only; the golden set stays
frozen as edition 1.

**Prerequisites** (Phase 3 items): the first measured run of classifier
prompt v1, the absolute floor set in `config/gate.yaml`, and the "nothing
changed" check (3 runs of v1, `docs/noise-check/`).

**Scenarios with a real PR** (each a normal PR through Flow 2, ≈ US$ 1.50 per
gate run; the gate has no special demo mode):

| # | Scenario | Version | Change in the YAML | Expected verdict | PR afterwards |
|---|---|---|---|---|---|
| 1 | Planted regression | v2 | "Simplified" prompt: category definitions and tie-break rules removed, labels kept | `blocked` by the category net drop; regressed cases listed | Closed unmerged (kept visible) |
| 2 | Judge stays advisory | v3 | Only the summary instructions change (e.g. "include concrete details" removed); classification unchanged | `warning` at most, never `blocked`; summary drop shown in the advisory row | Closed unmerged |
| 3 | Nothing changed | v4 | Identical to v1 except `version_id` and `change_note` | `passed`, no adversarial flips | Closed unmerged |
| 4 | Improvement | v5 | Refined definition of the category with the most misses in the v1 run | `passed`, improvements listed | **Merged**; v5 becomes the baseline |

How each one is created: a branch `scenario/<n>-<name>`; copy
`prompts/classifier/v1.yaml` to the new version file, make only the scenario's
change, set `version_id` and a `change_note` starting with "Scenario <n>:";
point `prompts/active.yaml` to it; open the PR titled `[Scenario <n>] …`.
Version numbers are never reused, even in closed PRs. Scenario 4 runs last,
because its merge changes the baseline. Step by step:
[`prompt-change.md`](../guides/prompt-change.md) ("Proof scenarios").

**Scenarios proved by unit tests** (hand-made case results fed to the verdict
function, no model calls, run by `checks.yml`):
- Cumulative drops: net drop 3, then another 3 that crosses the absolute
  floor → `blocked`.
- Inconclusive: 4 of 140 cases with infrastructure errors → `inconclusive`
  (exit 2).
- Adversarial flip: one adversarial case pass→fail → `blocked`.

**Rules that keep the proof honest:**
- The expected verdict is written in `docs/proof-scenarios.md` **before**
  anything is run, locally or in CI.
- `docs/proof-scenarios.md` records, per scenario: PR link, version,
  expected verdict, observed verdict, cost.
- A scenario that does not behave as expected is a finding and is recorded
  as observed.
- No threshold changes to make a scenario pass; thresholds change only by a
  recorded decision (3.5).
- Running a scenario locally first (Flow 1, `uv run eval`) is allowed to
  iterate; the evidence is the PR (check, comment, report artifact).

**Definitions.**
- *Mutation testing*: seeding deliberate faults ("mutants") into a program to
  check that the tests detect them; a detected mutant is "killed". Here the
  program is the prompt and the test suite is the gate.
- *Hand-made (fabricated) results*: a list written in the test saying which
  cases passed or failed on each side, so the verdict function is tested
  without calling the model.
- *Expected vs observed*: the verdict predicted before the run vs the one
  the gate produced.

**Why.**
- Mutation testing: deliberate, simple faults are seeded and the suite is
  judged by how many it kills [1]; the planted regression is a mutant the
  gate must kill.
- Test the grader with controls, including a response that must fail; if
  the controls fail, do not trust the score [2].
- Run the unchanged version before trusting a threshold (OpenRouter
  tutorial, already cited in 3.5): scenario 3 and the noise check.
- Removing only a tie-break rule (the earlier proposal) touches few
  ambiguous cases and may not reach the 7-case threshold, so the demo could
  fail without the gate being wrong; removing the definitions is a realistic
  "cleanup" change that affects many cases (our reasoning).
- Cumulative drops with real PRs would need several precisely sized
  degradations, each merged into `main` (filling `main` with bad prompts); a
  unit test proves the same floor rule without that (our reasoning).

**Considered, not adopted.** Cumulative drops with real PRs (costly, hard to
size, pollutes `main`); generating dozens of mutants automatically to compute
a kill rate (more rigor than a 140-case portfolio needs); a separate format
regression scenario (same net-drop rule, covered by unit tests).

## 6.2 Demo video

**Decision (2026-11-04).** A 3-minute video of scenario 1 (planted
regression) end to end, on the real PR. Proposed outline (revisited with Luis
when the stage arrives):

| Part | On screen | Point |
|---|---|---|
| Opening | One Excalidraw diagram: PR → baseline × candidate on 140 cases → verdict | Prompt changes ship unmeasured |
| The change | The `v2.yaml` diff (definitions removed) and the PR being opened | A harmless-looking cleanup |
| The gate | The GitHub check turning red; the PR comment (verdict, table, cases) | Why it blocked: net drop above 7 cases |
| The alert | Telegram on the phone: summary + attached report | Sound because it blocked; `passed` is silent |
| The report | HTML header, headline table, one regressed case open | How to read a case |
| Closing | Scenarios 3 and 4 green; the `docs/proof-scenarios.md` table | The gate also lets good changes through |

Recording rules: the CI wait is cut in editing; no secrets on screen (`.env`,
GitHub secrets page, bot token); everything shown is real (emails are
fictional by design); screen recording with voice, camera optional; any
recorder works. Language: Portuguese; hosted on YouTube and linked from the
README with a one-line English description.

**Considered, not adopted.** PT and EN recordings (double the work); a long
video in place of the demo (a long channel video is a channel decision; the
demo can become a segment of one later).

## 6.3 Write-up

**Decision (2026-11-04).** One text, two destinations:
1. `docs/write-up.md`, English, one page, linked from the README.
2. A LinkedIn post in Portuguese, written by Luis from the write-up,
   following his public-writing rules; links to the repository and the
   video.

Structure of `docs/write-up.md`:
1. The problem: is a 2-point drop after a prompt change real or noise?
2. What it is: email classifier, 140 handwritten cases, PR gate, Telegram
   alert.
3. How it measures: separate per-case verdicts; the judge only warns; the
   baseline is re-run in the same PR job.
4. Design decision in depth, signal vs noise: why count paired cases
   (regressions minus improvements), why 7 cases, the "nothing changed"
   numbers, and plainly that no statistical test is used — McNemar and
   bootstrap were considered and remain the upgrade path.
5. Proof: the expected vs observed table from `docs/proof-scenarios.md`
   with PR links, including any scenario that did not behave as expected.
6. Real numbers: cost per PR, CI run time, v1 accuracy, the floor.
7. Limits and next steps: one provider, one judge, small slices; in
   edition 1 language is confounded with the adversarial subtype
   (`phase-2-golden-dataset.md` 2.1).

Rules: written after the scenarios; every number comes from a real run and is
traceable to a repository file (`docs/proof-scenarios.md`,
`docs/noise-check/`, a report); only this project is mentioned; the README
carries a one-line credit to the BASWE guide (Project 1) and where the
project departs from it. Pre-publish checklist: numbers traceable, links
working, no secrets in any video frame.

**Definitions.**
- *McNemar test*: a statistical test that compares two classifiers on the
  same cases using only the cases where they disagree.
- *Bootstrap*: resampling the cases many times to estimate the margin of
  error of a metric.

**Why.** The BASWE guide asks for a 3-minute end-to-end walkthrough (more
persuasive than a README) and a short write-up with the problem, the approach
and one design decision [3]. Its example decision, slow drift, was removed
from this project with the scheduled runs, so signal vs noise is the
decision written in depth; it is the central question of planning §2.

**Considered, not adopted.** A separate blog (duplicates the write-up);
"slow drift" as the main decision (removed from the project).

## References

1. University of Luxembourg — Mutation Testing Theory. https://mutationtesting.uni.lu/theory.php
2. OneUptime — How to Turn LLM Evaluation into a Reliable CI Regression Gate (2026-08-31). https://oneuptime.com/blog/post/2026-08-31-llm-evaluation-ci-regression-gate/markdown
3. BASWE — 15 AI Engineering Projects That Actually Land Jobs, Project 1, Phase 6 (guide PDF, local copy).
