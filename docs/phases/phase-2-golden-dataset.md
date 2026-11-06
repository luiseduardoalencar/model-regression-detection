# Phase 2 — Golden dataset

**Goal:** golden edition 1 — about 140 hand-written, human-verified cases
that make a fair, hard-enough exam for the classifier, frozen and versioned.

**Status:** all decisions taken (2.1–2.6). 140 cases drafted and reviewed in
`golden/drafts/edition-1.json` (2026-11-04, review items R1–R5 resolved);
validation script, label audit, intra-annotator check and freeze pending
(they need code). Edition 1 stays frozen once released: tests and demos
change prompts only (decisions 5.1, 6.1).
Implementation checklist: [`planning.md` §7, Phase 2](../planning.md#phase-2--golden-dataset).
Manual procedures: [`guides/`](../guides/).

## Already fixed before this phase

- Data in Brazilian Portuguese; ~10 % English/mixed; summaries always
  Portuguese ([`foundations.md`](../foundations.md) F4).
- Case fields, `acceptable_categories`, three-way category scoring, one file
  per frozen edition: [`planning.md` §4](../planning.md#golden-file).
- Authoring loop: Claude sends a case brief, Luis writes the email and the
  summary, Claude structures the JSON, Luis confirms label and difficulty —
  [`guides/golden-case-authoring.md`](../guides/golden-case-authoring.md).
- Public datasets are inspiration for wording only, never copied:
  Bitext (CDLA-Sharing-1.0) [15], Tobi-Bueck (CC BY-NC 4.0) [16]. Other
  implementations of this BASWE project on GitHub have no license and are
  references for structure only (e.g. the `category_any` idea behind
  `acceptable_categories`) [17].

## 2.1 Coverage matrix

**Decision.** Per category (all 7): 14 `typical`, 4 `edge`, 2 `adversarial`,
0 `known_failure` → 20 per category, 140 total. Cross-cutting: ~10 %
English/mixed in every case type; at least 25 % `hard` (≥ 35). New case field
`case_type`.

**Why.**
- Separate samples by purpose (golden/typical, edge, adversarial, known
  failures); cover every output category; make 20–30 % genuinely hard;
  100–500 samples for a single feature [1].
- Bucket mix with production sample, adversarial, edge and failure replays;
  if a bucket reaches zero "the gate stops gating"; 5–10 cases per cell [2].
- Dimensions must target anticipated failures, not arbitrary variation [3].
- No production traffic here, so "production sample" becomes typical cases
  written with varied customer profiles; known failures start empty and fill
  edition 2.

**Statistical limit.** About 400 samples are needed to detect a 5-point
accuracy difference at 95 % confidence with independent samples [1]. With 140
cases, large regressions (≈ 8+ points) are detectable; small ones are
warnings, and cumulative small drops are caught by the absolute floor (3.4). The comparison is paired, which is more sensitive
(method in Phase 3).

**Exact vs approximate targets (decided 2026-11-05).** The validation script
flags only exact targets: counts per category and case type, each edge type
at least twice, the adversarial subtypes, ≥ 35 `hard`; these block freezing.
Approximate targets — "~10 % English/mixed in every case type" and the
difficulty mix per type (2.3) — are printed as information, never as flags.

*Why.* The draft meets the overall share (14 / 140) and every difficulty
target, but per type it has 3 / 98 `typical`, 4 / 28 `edge` and 7 / 14
`adversarial` English/mixed. The wording is approximate by design, and a
warning that stays on every run teaches people to ignore warnings.
Considered, not adopted: a warning.

*Known limitation of edition 1.* Language is confounded with the
adversarial subtype: all 6 `label_forcing` cases are English, all 6
`prompt_injection` cases are Portuguese, and 7 of the 9 English cases are
adversarial (the 5 mixed cases are 4 `edge` and 1 `typical`). When two
features always appear together, an effect cannot be attributed to either
one [19]: if `label_forcing` cases fail, the report cannot say whether the
cause is the language or the forcing attempt. Luis kept edition 1 as it is
because slices are advisory (Phase 3) and the adversarial invariant covers
all 14 cases in any language, so the gate verdict is unaffected; the
limitation goes to the write-up's limits and is a candidate fix for
edition 2. Considered, not adopted: rewriting cases before the freeze.

## 2.2 Edge and adversarial types

**Decision.** Values of `edge_types`:

| Type | Definition | Basis |
|---|---|---|
| `ambiguous` | Fits two categories; the tie-break rule decides | Tie-break rules |
| `temporal` | Timing changes the category | CheckList — temporal [4] |
| `negation` | A negation flips the apparent meaning | CheckList — negation [4] |
| `confounder` | Another category's vocabulary, but one clear request | CheckList — vocabulary [4] |
| `multiple_requests` | More than one request; the main action decides | Master rule |
| `very_short` | One to five words | Apple — very short inputs [1] |
| `long_thread` | Long or forwarded email, request buried inside | Apple — unusual formatting [1] |
| `typos` | Heavy typos, abbreviations, no punctuation | CheckList — robustness [4] |
| `sarcasm` | Real meaning opposite to the literal one | BASWE guide |
| `mixed_language` | Portuguese and English mixed | Language decision |
| `prompt_injection` (adversarial) | Instructions to the classifier inside the email, incl. fake JSON; answer = the real request | OWASP LLM01 [5] |
| `label_forcing` (adversarial) | Customer tries to force the routing; answer = the real request | OWASP LLM01 [5] |
| `out_of_scope` (adversarial) | Not a buyer support request; answer = `general` | CLINC150 out-of-scope [6] |

Distribution: each edge type at least twice among the 28 edge cases;
`ambiguous`, `temporal`, `negation` concentrated on the hard boundaries;
a case may carry several types. Two adversarial cases per category
(`prompt_injection` or `label_forcing`), except `general`, whose two are
`out_of_scope`. Future: CheckList invariance tests generated by code.

## 2.3 Difficulty rubric

**Decision.** Rubric based on observable features of the email
([`planning.md` §4](../planning.md#golden-file)); practical test for `hard`:
an attentive human agent would hesitate. `typical` mostly `easy`/`medium`,
`edge` mostly `medium`/`hard`, `adversarial` almost always `hard`. After the
first runs, **observed difficulty** (how often a case fails across prompt
versions) is computed from run history and mismatches are flagged for
edition 2. Difficulty never affects the score.

**Why.** Easy2Hard-Bench estimates difficulty from real performance data
(IRT, Glicko-2) instead of human guesses [7]; human-perceived and model
difficulty correlate below 0.5 [8]. Expected difficulty is therefore a
hypothesis to be checked.

## 2.4 Summary guide

**Decision.** Ten rules in [`summary-guide.md`](../summary-guide.md), the
single source for the golden references, the classifier prompt's summary
instructions and the judge rubric.

**Why.** SummEval scores summaries on consistency (no hallucinated facts),
relevance, coherence and fluency [9]; support-handoff practice puts the
request first and keeps concrete, verifiable details [10]. Using one guide in
three places keeps the system from measuring one thing and asking for another.

## 2.5 Label quality control

**Decision.**
- **Label audit:** `gpt-6.1-terra` with 3 prompt variants re-labels every
  case; cases where the 3 agree with each other and disagree with Luis are
  flagged; Luis resolves each flag. The LLM never writes a label.
- **Intra-annotator check:** days later, Luis blindly re-labels 20 random
  cases; Cohen's kappa ≥ 0.7, otherwise revise the taxonomy before freezing.
- **Freeze criteria:** validation passes, all audit flags resolved,
  kappa ≥ 0.7; the header records taxonomy and summary-guide versions and the
  audit date.

**Why.** Popular ML test sets contain at least 3.3 % label errors on average
and the errors change model rankings [11]. An LLM ensemble that flags
confident disagreements, followed by expert review, found 6–21 % label errors;
above 95 % confidence, more than two-thirds of flags were human errors [12].
Kappa below 0.7 means the guidance must be fixed before scaling [2].

Procedures: [`guides/label-audit.md`](../guides/label-audit.md),
[`guides/intra-annotator-check.md`](../guides/intra-annotator-check.md).

## 2.6 Duplicate detection

**Decision.** Within the golden set and between the golden set and the
few-shot examples:

| Layer | Method | Rule |
|---|---|---|
| Exact | Hash of normalized text (NFKC, casefold, no punctuation, collapsed whitespace) | Blocks |
| Lexical | `rapidfuzz.token_sort_ratio` | ≥ 90 blocks; 80–90 warns; < 5 words → exact check only |
| Semantic | Cosine of OpenAI embeddings (model ID in config) | ≥ 0.92 warns |
| Label conflict | Lexical/semantic pair with different `expected_category` | Highest-priority flag |

Thresholds are checked against a crafted fixture of pairs in unit tests,
never tuned on the golden set.

**Why.** Dedup practice uses three layers with strategy-specific thresholds
(TF-IDF cosine 0.9 conservative, embeddings 0.85–0.95) and warns against
tuning on the test set [13]; MinHash thresholds of 0.7–0.85 are common
(FineWeb 0.85) [14]; semantic near-duplicates skew the distribution toward a
single scenario [1]. `token_set_ratio` was rejected because it scores 100 when
one text is contained in the other [18].

Procedure for flags: [`guides/validation-flags.md`](../guides/validation-flags.md).

## References

1. Apple — Designing datasets to test your feature (Evaluations) — https://developer.apple.com/documentation/evaluations/designing-evaluation-datasets
2. FutureAGI — LLM Eval Golden Set Design: A 2026 Engineering Guide — https://futureagi.com/blog/llm-eval-golden-set-design-2026/
3. Hamel Husain — Generate synthetic data (evals skills) — https://skills.sh/hamelsmu/evals-skills/generate-synthetic-data
4. Ribeiro et al., *Beyond Accuracy: Behavioral Testing of NLP Models with CheckList* (ACL 2020) — https://homes.cs.washington.edu/%7Emarcotcr/acl20_checklist.pdf ; summary — https://amitness.com/2020/07/checklist/
5. OWASP Top 10 for LLM Applications 2025 (explanation) — https://dev.to/kuboidsecurelayer/owasp-top-10-for-llm-applications-2025-plain-english-explanation-with-real-examples-2i7f
6. CLINC OOS — TensorFlow Datasets — https://www.tensorflow.org/datasets/catalog/clinc_oos
7. Easy2Hard-Bench (NeurIPS 2024) — https://proceedings.neurips.cc/paper_files/paper/2024/hash/4e6f22305275966513990f53cec908e0-Abstract.html
8. *Can LLMs Estimate Student Struggles?* (arXiv 2512.18880) — https://alphaxiv.org/overview/2512.18880v1
9. Fabbri et al., *SummEval* (arXiv 2007.12626) — https://arxiv.org/pdf/2007.12626
10. Supportbench — How to reduce handoff mistakes with structured summaries — https://www.supportbench.com/?p=25204
11. Northcutt et al., *Pervasive Label Errors in Test Sets Destabilize ML Benchmarks* (arXiv 2103.14749) — https://arxiv.org/abs/2103.14749
12. *Are LLMs Better than Reported? Detecting Label Errors* (arXiv 2410.18889) — https://arxiv.org/html/2410.18889v2
13. eval-toolkit — Text deduplication methodology — https://brandon-behring.github.io/eval-toolkit/methodology/text_dedup.html
14. ZeroEntropy — Deduplication — https://www.zeroentropy.dev/concepts/deduplication/
15. Bitext customer support dataset (README) — https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/blob/main/README.md
16. Tobi-Bueck customer-support-tickets (README) — https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/main/README.md
17. Example implementation of the same BASWE project (golden dataset PR) — https://github.com/onkar-thete-04/model_regreesion_detection_system/pull/2
18. RapidFuzz — fuzzy matching functions — https://tessl.io/registry/tessl/pypi-rapidfuzz/3.14.0/files/docs/fuzzy-matching.md
19. Wikipedia — Confounding — https://en.wikipedia.org/wiki/Confounding
