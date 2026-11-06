# Phase 3 — Evaluation engine

**Goal:** run the exam, score every case on several dimensions, compare with
the baseline and say whether the candidate regressed — separating real
changes from noise.

**Status:** decisions 3.1–3.6 taken. Not implemented yet.
Implementation checklist: [`planning.md` §7, Phase 3](../planning.md#phase-3--evaluation-engine).

## Already fixed before this phase

- Async runner with a concurrency limit; retries come from the OpenAI SDK;
  failure types, inconclusive runs and judge failures (Phase 1, decision 1.6).
- Judge model `gpt-6.1-terra` through the `LLMClient` port; response cache as
  `CachingLLMClient`; per-run records in `RunRepository`; local runs recorded
  as Langfuse experiments.

## 3.1 Classification metrics

**Decision.**
- Two headline numbers: **strict accuracy** (exact label) and **acceptable
  accuracy** (exact or in `acceptable_categories`).
- Per-category **precision, recall, F1** and **macro-F1**, strict labels only,
  via scikit-learn `classification_report`.
- **Confusion matrix** 7×7 plus a "no answer" column (refusal / incomplete /
  invalid); infrastructure errors excluded.
- Strict and acceptable accuracy **sliced** by `case_type`, difficulty, edge
  type and language, always with the slice size (small slices are alarms).

**Definitions.**
- *Precision* of a category: of the emails the model put in it, the share
  that belonged there. *Recall*: of the emails that belonged there, the share
  the model found. *F1*: harmonic mean of the two. *Macro-F1*: unweighted mean
  of the per-category F1 (every category counts equally).
- *Confusion matrix*: rows = expected category, columns = predicted category;
  off-diagonal cells show which categories are confused.

**Why.** `classification_report` is the industry standard (per-class
precision, recall, F1, support; macro and weighted averages; micro = accuracy
in multiclass) [1]; Anthropic's classification guide evaluates the same way
plus a confusion matrix [2]. The golden set is balanced (20 per category), so
accuracy is not distorted by a dominant class and the weighted average equals
the macro average. Precision/recall have no clean definition with acceptable
labels, so F1 uses strict labels. The strict/acceptable split, the "no
answer" column and the slices follow from our own decisions (1.6, 2.1–2.3).

## 3.2 Summary judge

**Decision.**
1. **Code checks first:** one sentence; starts with "Cliente"; no category
   label; Portuguese.
2. **Binary checklist** derived from [`summary-guide.md`](../summary-guide.md),
   one item per prompt:

   | Item | Question (yes/no, with evidence) | Critical |
   |---|---|---|
   | `faithful` | Only facts stated in the email? Nothing invented? | Yes |
   | `main_request` | States the customer's main request? | Yes |
   | `key_fact` | Includes the essential fact behind the request? | No |
   | `concrete_details` | Keeps the relevant order number, amount, date, product when given? (n/a otherwise) | No |
   | `neutral_tone` | Neutral tone, no insults or irony reproduced? | No |
   | `ignores_injection` | Adversarial only: ignores injected instructions? | Yes |

   The judge sees the email, the expected summary and the generated summary
   (reference-guided) and cites evidence per item.
3. **Scores computed outside the model:** `summary_pass` = all critical items
   and all code checks pass; `summary_score` = pass rate of applicable items.
4. **DeepEval:** one `GEval` per item, explicit `evaluation_steps`, binary via
   `strict_mode` (confirm against the current version; fallback `DAGMetric`),
   judge model through our port, `reasoning_effort: none`, `temperature: 0`,
   versioned in `prompts/judge/v1.yaml` (Portuguese).
5. **Cost:** ~5 judge calls per case, ~US$ 0.75 per full run (estimate). The
   eval cost does not grow with production traffic; judging live traffic
   would use sampling.

**Why.**
- G-Eval scores each dimension with its own prompt; direct integer scores
  create many ties, so the original weights scores by token probabilities;
  authors warn of a bias toward LLM-generated text [3][4].
- DeepEval's `GEval` supports `criteria` / `evaluation_steps`, `rubric`,
  `threshold`, `strict_mode` and a custom `model` [5].
- Binary pass/fail beats 1–5 scales: adjacent points are subjective, raters
  drift to the middle, scales need larger samples; gradual progress is
  tracked with binary sub-criteria [6].
- "Asking an LLM to directly assign a single 1-5 score is a fragile
  measurement design": deterministic checks first, binary checklists,
  evidence per item, aggregate outside the model; a pass rate is a legitimate
  proportion [7].
- Considered and not adopted as the main score: pairwise judging
  (baseline vs candidate). Pairwise preferences flipped in ~35 % of cases vs
  9 % for absolute scores under manipulation [8], and position bias grows when
  the two answers are close [9] — exactly the regression case.

## 3.3 Judge calibration

**Decision.**
- Calibration set: 100 generated summaries judged by Luis — 60 from
  classifier prompt v1, 40 from a deliberately degraded prompt (so failures
  are measurable). Luis records overall pass/fail, `faithful`,
  `main_request` and a short critique on fails.
- Split 15 train (critiques become examples in the judge prompt) / 45 dev
  (iterate) / 40 test (run once at the end).
- Metrics on test: TPR and TNR separately, Cohen's kappa, verdict flip rate
  over 3 runs. Targets: TPR ≥ 0.85 and TNR ≥ 0.85 (our choice).
- The judge is always advisory (3.4, amended); if the targets are missed,
  the report marks summary results as uncalibrated.
- Recalibrate when the judge model or judge prompt changes (re-run the
  labeled test set).
- Optional: compare PT vs EN judge prompts on dev.

**Definitions** (positive = "pass"):
- *TPR* (true positive rate, sensitivity): of the summaries Luis passed, the
  share the judge also passed. Low TPR → good summaries rejected (false
  alarms in the gate).
- *TNR* (true negative rate, specificity): of the summaries Luis failed, the
  share the judge also failed. Low TNR → bad summaries pass — the most
  dangerous error for a regression detector.
- *Raw agreement* hides a judge that passes everything (95 % agreement with
  5 % failures and zero failures caught).
- *Cohen's kappa*: agreement beyond chance; 1 perfect, 0 chance level.
- *Flip rate*: share of verdicts that change across repeated runs on the
  same items (noise, not correctness).

Worked example and procedure: [`guides/judge-calibration.md`](../guides/judge-calibration.md).

**Why.**
- Pick a principal domain expert; binary pass/fail with critiques; ~100
  examples (below 60 the confidence intervals are too wide); train/dev/test
  splits with test kept hidden; report TPR and TNR separately; >90 %
  agreement reached in three iterations in a real case [10].
- Criteria drift: "users need criteria to grade outputs, but grading outputs
  helps users define criteria" — labeling will refine the summary guide [11].
- Judge self-agreement of 91 % fell to 64 % against human labels in one
  team; temperature 0 does not guarantee identical verdicts [12].
- LLM judges reach > 80 % agreement with humans, the same level as
  human-human agreement, but show position, verbosity and self-enhancement
  biases [13]. Multilingual judging is inconsistent (Fleiss kappa ≈ 0.3);
  English prompts are common but untested against native-language prompts
  [14] — hence the optional PT vs EN comparison.

## 3.4 Case pass rule and what blocks the PR

**Decision.**

1. **Per-case verdicts, kept separate** (no combined score):

   | Verdict | Rule | Nature |
   |---|---|---|
   | `category_pass` | Predicted label is the expected one or is in `acceptable_categories` | Deterministic |
   | `format_pass` | Code checks of 3.2 pass (one sentence, starts with "Cliente", no category label, Portuguese) | Deterministic |
   | `summary_pass` | All critical checklist items + code checks pass (3.2) | Judge-dependent |

   No answer (refusal / incomplete / invalid) fails all three (1.6).
   Infrastructure errors are excluded from both sides (1.6).

2. **Run verdicts and exit codes:**

   | Verdict | When | Exit code |
   |---|---|---|
   | `passed` | No rule fired | 0 |
   | `warning` | Only advisory rules fired | 0 (plus notice) |
   | `blocked` | At least one blocking rule fired | 1 |
   | `inconclusive` | Infrastructure errors > 2 % (1.6) | 2 (distinct "re-run" message) |

3. **What blocks and what is advisory:**

   | Signal | Role |
   |---|---|
   | `category_pass` rate (acceptable accuracy) | Blocks on a drop beyond the critical threshold (3.5) |
   | Adversarial cases, `category_pass` | Blocks on any pass→fail (invariant); demoted to advisory if the noise measurement (3.5) shows flips with nothing changed |
   | `format_pass` rate | Blocks on a drop beyond the critical threshold (3.5) |
   | Absolute floor on acceptable accuracy and `format_pass` | Blocks when below; value set after the first measured run of classifier prompt v1; changes only by a recorded decision |
   | `summary_pass` rate | Advisory (the judge never blocks, point 4) |
   | `summary_score`, strict accuracy, macro-F1, per-category metrics, slices | Advisory (warnings per 3.5; slices always with n) |
   | Latency, tokens, cost | Advisory: deltas shown, never block |

4. **The judge is always advisory** (amended 2026-11-04, replacing a
   "judge promotion" rule): it can produce `warning`, never `blocked`. This
   removes promotion criteria and re-judging of flipped verdicts.

**Definitions.**
- *Pass rate*: passed cases ÷ valid cases. With 140 cases, one case =
  0.71 percentage points; within a category (20 cases), one case = 5 points.
- *Percentage points (pp)*: absolute difference between two percentages
  (91 % → 88 % = −3 pp).
- *Regression / improvement*: a case that passes in the baseline and fails in
  the candidate (pass→fail), or the reverse.
- *Deterministic*: the same output always gets the same verdict (category,
  format checks); the judge is not deterministic.
- *Exit code*: the number a program returns; GitHub Actions treats 0 as
  success and anything else as failure. A *required status check* (Phase 5)
  prevents merging while the check fails.
- *Regression eval vs capability eval*: a regression eval checks that what
  worked still works and should sit near 100 %; a capability eval measures how
  far the system can go and starts low.
- *Invariant (hard constraint)*: a rule no average can compensate.
- *Relative tolerance vs absolute floor*: "did it get much worse than the
  last version?" vs "is it still above the minimum?". The floor stops
  cumulative drift (several small drops, each under the threshold).
- *Shadow / advisory mode*: the check runs and is reported but does not
  decide the merge.

**Why.**
- A case passes only if all its checks pass in DeepEval (any metric below its
  threshold fails the case; the run exits with code 1) [16] and in Promptfoo
  by default; `weight: 0` records a metric without making it block [17].
- Separate exit codes for "got worse" (1) and "could not run" (2), so a
  provider outage is not read as a regression; an LLM judge never fails a
  build on its own until its verdicts are checked against human grading;
  thresholds set from runs of the unchanged `main` [18].
- Hard constraints that a high average cannot offset; both a maximum
  regression and an absolute floor per metric; new gates start in shadow
  mode [19].
- Only checks that never change verdict on unchanged input should block;
  judge scores stay advisory; a gate that blocks clean PRs trains people to
  force-merge [15].
- Regression evals target near-100 % pass rates; graders can be combined by
  weighting or by requiring all to pass [20].
- Strict accuracy stays in the report: `acceptable_categories` exists for
  genuinely ambiguous cases, so blocking on strict labels would put
  self-inflicted noise into the gate (our reasoning, from 2.1–2.3).
- Per-category metrics do not block: n = 20 per category, so one case moves
  the metric by 5 points; monitoring per-class metrics and macro-F1 as
  regression signals that trigger review matches classifier practice [21].

## 3.5 Signal vs noise

**Decision (lean version, chosen for the project's size).**

| Verdict | Rule (on `category_pass` and `format_pass`) |
|---|---|
| `warning` | Net drop ≥ 5 cases (≈ 3.5 pp) |
| `blocked` | Net drop ≥ 7 cases (5 pp); also any adversarial pass→fail and the absolute floor (3.4) |

- Thresholds live in versioned config (`config/gate.yaml`, together with the
  absolute floor and the golden edition in use; decision 5.1) and replace
  the guide's provisional 3 % / 8 %.
- **"Nothing changed" check:** once, when classifier prompt v1 exists, run it
  3 times with the cache bypassed (≈ US$ 2.25); confirm that no threshold
  fires and no adversarial case flips. Repeat only if the model changes.
  If it shows flips, adjust then (raise thresholds or add re-runs of the
  changed cases) and record the change. Report in `docs/noise-check/`.
- Considered and not adopted: McNemar exact test, bootstrap confidence
  intervals, confirmation re-runs by default — more rigor than a 140-case
  PR gate needs; they remain the upgrade path if the check shows flips.

**Definitions.**
- *Paired comparison*: both sides are scored on the same cases and compared
  case by case (regressions and improvements), instead of comparing two loose
  averages.
- *Net drop*: regressions (pass→fail) minus improvements (fail→pass), in
  cases. With 140 cases, 7 cases = 5 percentage points.
- *Noise*: differences that appear with nothing changed, because model
  outputs vary slightly even at temperature 0. With 140 cases, a difference
  of 1–3 cases can be plain noise — hence the threshold at 7.

**Why.**
- When two versions answer the same questions, analyse paired differences:
  it removes the variation in question difficulty [23].
- Run the unchanged version several times before trusting a threshold; a
  threshold above what unchanged runs produce blocks PRs that changed nothing
  [18].
- Measure variance before setting thresholds, but start from the smallest
  regression that matters; use exact counts and hard invariants for critical
  cases [24].

**How it is tested.** Unit tests feed hand-made case results to the verdict
function (7 regressions → `blocked`; 4 → `passed`; an adversarial
regression → `blocked`; 3 % infra errors → `inconclusive`; two small drops
crossing the absolute floor → `blocked`); end to end by the Phase 6 scenarios
(decision 6.1: planted regression blocked, summary-only change never
blocked, same prompt passes, improved prompt passes with improvements
listed).

## 3.6 Baseline and per-case diff

**Decision.**
- **Baseline = the active prompt on `main`, re-run in the same PR job** next
  to the candidate. Both sides use the same model at the same moment, the
  same golden edition, judge prompt and scoring code, so the difference comes
  only from the PR. Nothing has to be stored for the gate (Phase 5 decision
  5.2 is likely unnecessary). Cost ≈ US$ 1.50 per PR.
- Cases are **paired by `id`** (stable, never reused).
- **Diff content** (visual format in Phase 4):
  1. Header: "classifier prompt v3 (candidate) vs classifier prompt v2
     (baseline), golden edition 1, judge prompt v1", verdict and reason.
  2. Headline table: baseline, candidate, delta (pp), regressions,
     improvements — for category, format and summary (summary marked
     advisory).
  3. Lists by severity: violated invariants; category regressions; format
     regressions; summary regressions; improvements; exact→acceptable
     changes; infra errors excluded from the comparison.
  4. Each case: `id`, expected category, label before → after, summary
     before → after, judge evidence per item.
  5. Per-category and slice deltas with n; rows with a net drop ≥ 2 cases
     highlighted (they do not change the verdict).
  6. Count of cases whose output changed without a verdict change.
- In CI the tracer is a no-op (Langfuse is local), so the HTML report must be
  self-contained; locally, each run is also a Langfuse experiment and can be
  compared in its comparison view.

**Definitions.**
- *Baseline*: the approved reference the candidate is measured against.
- *Candidate*: the prompt version under review in the PR.
- *Same job*: both sides run together in one CI execution.

**Why.**
- Choose the reviewed release run as the baseline — a newer run is not
  automatically an approved baseline; an improvement in the average can hide
  a regression on a critical case, so inspect cases, not only averages [25].
- Per-score regression and improvement counts, rows matched by a key, the
  most affected rows first, per-case diffs [22].
- Running both sides together isolates the prompt change: if the provider
  updates the model, both sides change together and the PR is not blamed
  (our reasoning; there are no scheduled runs in this project).

## References

1. scikit-learn — `classification_report` (1.9.1) — https://scikit-learn.org/stable/modules/generated/sklearn.metrics.classification_report
2. Anthropic — Classification guide (cookbook) — https://platform.claude.com/cookbook/capabilities-classification-guide
3. Liu et al., *G-Eval* (EMNLP 2023) — https://aclanthology.org/2023.emnlp-main.153
4. G-Eval full text — https://ar5iv.labs.arxiv.org/html/2303.16634
5. DeepEval — custom metrics (GEval, DAGMetric) — https://tessl.io/registry/tessl/pypi-deepeval/files/docs/custom-metrics.md
6. Hamel Husain — Why binary pass/fail instead of 1–5 ratings — https://hamel.dev/blog/posts/evals-faq/why-do-you-recommend-binary-passfail-evaluations-instead-of-1-5-ratings-likert-scales.html
7. Microsoft — Better LLM scoring whitepaper (June 2026) — https://microsoft.github.io/mcscatblog/assets/posts/better-llm-scoring/20260626_LLM1-5Scoring_WhitePaper.pdf
8. *Pairwise or Pointwise? Evaluating Feedback Protocols for Bias* (arXiv 2504.14716) — https://www.emergentmind.com/papers/2504.14716
9. *Judging the Judges: A Systematic Study of Position Bias* (arXiv 2406.07791) — https://arxiv.org/abs/2406.07791
10. Hamel Husain — Using LLM-as-a-Judge for evaluation: a complete guide — https://hamel.dev/blog/posts/llm-judge/index.html
11. Shankar et al., *Who Validates the Validators?* (UIST 2024) — https://arxiv.org/abs/2404.12272
12. Christoph — Your AI judge needs a judge — https://schristoph.online/blog/your-ai-judge-needs-a-judge/?utm=series
13. Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (NeurIPS 2023) — https://neurips.cc/virtual/2023/poster/73434 ; https://arxiv.org/abs/2306.05685
14. Fu and Liu, *How Reliable is Multilingual LLM-as-a-Judge?* (EMNLP 2025 Findings) — https://arxiv.org/html/2505.12201v1
15. *We gated CI on six open-source LLM eval frameworks* — https://dev.to/ethanwritesai/we-gated-ci-on-six-open-source-llm-eval-frameworks-only-two-survived-the-merge-queue-5elf
16. theneuralbase — DeepEval passing and failing thresholds — https://theneuralbase.com/deepeval/learn/beginner/passing-and-failing-thresholds/
17. Promptfoo — Assertions and metrics (weights, `threshold`) — https://www.promptfoo.dev/docs/configuration/expected-outputs/
18. OpenRouter — How to gate pull requests on LLM evals in CI — https://openrouter.ai/blog/tutorials/how-to-gate-pull-requests-on-llm-evals-in-ci/
19. OneUptime — How to turn LLM evaluation into a reliable CI regression gate (2026) — https://oneuptime.com/blog/post/2026-08-31-llm-evaluation-ci-regression-gate/view
20. Anthropic — Demystifying evals for AI agents (mirror) — https://learn-anthropic.pages.dev/en/articles/engineering/demystifying-evals-for-ai-agents
21. FutureAGI — Evaluating LLM classifiers (2026) — https://futureagi.com/blog/evaluating-llm-classifiers-2026/
22. Braintrust — Compare experiments — https://www.braintrust.dev/docs/evaluate/compare-experiments
23. Anthropic — A statistical approach to model evaluations (Miller, *Adding Error Bars to Evals*) — https://www.anthropic.com/research/statistical-approach-to-model-evals ; https://arxiv.org/abs/2411.00640
24. OneUptime — Measure variance before setting thresholds (2026) — https://oneuptime.com/blog/post/2026-08-31-measure-llm-eval-variance-thresholds/view
25. Langfuse — Compare experiments — https://langfuse.com/docs/evaluation/experiments/compare-experiments
