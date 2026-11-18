# Lessons learned

A running log of the problems met while building this project: decisions that
did not hold against real data, tools that behaved differently than expected,
measurements that misled, and process or security slips. It is the raw
material for content (videos, posts, the write-up), so each entry keeps the
evidence and the takeaway.

**What goes here.** A problem that changed a decision, a number or a
procedure. **What does not.** Typos, lint errors, wrong file names, failed
tests from typing the code: those are fixed and forgotten.

**Entry format.** Date and build step · what we expected · what happened (with
numbers) · why · what we decided (link to `planning.md` §12) · takeaway.

---

## 2026-11-06 · Step 1 · Build steps cross phases, checklists do not

- **Expected.** Each build step would tick boxes of the phase checklist
  (`planning.md` §7).
- **What happened.** Step 1 built part of three boxes of two phases (output
  models of Phase 1, schema and fixture of Phase 2). None could be ticked:
  a checkbox has no "partly done".
- **Why.** Phases group *decisions* by subject; build steps group *work* by
  what can be tested together. The two cuts do not line up.
- **Decided.** A box is ticked only when complete; partial progress is a dated
  status line under the box ("Partial progress in §7", §12).
- **Takeaway.** Plan by decision, build by testable increment, and give the
  tracker a way to say "partly".

## 2026-11-06 · Step 2 · One status for two different failures

- **Expected.** `LLMResult.status` with `completed / incomplete / refusal /
  error` (decision 1.5) was enough.
- **What happened.** Decision 1.6 says invalid output (bad JSON) is a
  classifier miss, while an API failure is not a miss and counts toward the
  2 % limit that makes a run inconclusive. Both would have been `error`.
- **Why.** Two decisions written days apart, each correct alone, collided in
  the shared type.
- **Decided.** New status `invalid_output`; `error` only for infrastructure
  (§12).
- **Takeaway.** Read the data model against every rule that consumes it
  before coding; a type shared by two rules must separate what they treat
  differently.

## 2026-11-06 · Step 2 · Cost without the cache price

- **Expected.** `pricing.yaml` with input and output price per model.
- **What happened.** The API reports cached input tokens at a tenth of the
  price (`gpt-6-luna`: US$ 0.01 vs 0.10 per 1M). Without that line every
  cached call would be over-reported.
- **Decided.** `cached_input` per model; a model missing from the table stops
  the run instead of costing zero (§12). LiteLLM's public price map prices
  unknown models at US$ 0 silently, the failure we chose to avoid.
- **Takeaway.** Cost tracking needs the provider's whole price shape, and a
  missing price must be loud.

## 2026-11-06 · Step 2 · The SDK helper that hides the evidence

- **Expected.** `responses.parse` (OpenAI SDK) would return the parsed object
  or a status.
- **What happened.** In openai 3.45.0 it raises an exception when the text does
  not match the schema, including answers cut by `max_output_tokens`. The
  `incomplete` status, the token usage (cost) and the request ID are lost
  exactly when they matter.
- **Decided.** Call `responses.create` with the same strict schema and parse
  ourselves (§12).
- **Takeaway.** Convenience helpers are optimized for the happy path; an
  evaluation system lives in the unhappy one. Read the helper's code before
  trusting it with failures.

## 2026-11-07 · Step 3 · A threshold from the literature that caught nothing

- **Expected.** Cosine ≥ 0.92 between embeddings flags semantic near-duplicates
  (decision 2.6, from dedup guides quoting 0.85–0.95).
- **What happened.** With `text-embedding-3-large`, crafted paraphrases scored
  0.745–0.875 and unrelated pairs 0.300–0.451. At 0.92 the layer flagged
  nothing; on the golden set it reported "0 flags", which looked like a clean
  dataset but meant a blind detector.
- **Why.** Cosine scales depend on the embedding model: newer OpenAI models
  give much lower similarities than `ada-002`, the model many published
  thresholds came from.
- **Decided.** Measure first: 23 crafted pairs (10 paraphrases, 7 minimal
  pairs, 6 unrelated), never the golden set. Threshold 0.74, the highest value
  that catches every paraphrase with no unrelated pair warning (§12). The
  golden set then showed 27 warnings (5 label conflicts, 22 semantic pairs).
- **Takeaway.** A threshold is a property of the model, not of the method.
  "Zero findings" from a detector that was never shown to fire is not
  evidence of anything: test the detector on cases where it must fire.
- **Rule.** Every threshold, cutoff or score limit is checked against crafted
  cases that must and must not trigger it, with the model actually used,
  before its output is trusted.

## 2026-11-07 · Step 3 · Embeddings measure the topic, not the request

- **What happened.** "Quero cancelar meu pedido, ele ainda não chegou" ×
  "Quero cancelar meu pedido, mas ele chegou ontem" scored 0.803, more similar
  than 6 of the 10 true paraphrases, although the two belong to different
  categories (`cancellation` × `return_refund`). The 7 minimal pairs (one per
  tie-break rule) spread over 0.565–0.803, overlapping the paraphrases.
- **Why.** Most of the text is shared; the clause that decides the category is
  a small part of the vector.
- **Decided.** No threshold can separate them, so minimal pairs are printed,
  never asserted; those above 0.74 surface as label conflicts, and the LLM
  label audit covers the rest (§12).
- **Takeaway.** Semantic similarity answers "same subject?", not "same
  intent?". Use it to find candidates for review, never to decide a label.

## 2026-11-07 · Step 3 · Label conflicts born from reused templates

- **What happened.** The first real semantic run flagged 5 label conflicts in
  3 groups. Two came from writing templates: `return_refund-008` ×
  `payment-008` share the same prompt-injection paragraph word for word (only
  the fake JSON changes), and `cancellation-005` × `return_refund-005` share
  the same persona, opening and closing. The third group is the
  `delivery` × `cancellation` boundary itself (`delivery-009`,
  `cancellation-004`, `cancellation-011`, `delivery-021`).
- **Decided.** All labels kept; each case's `notes` records what separates it
  from its neighbour and which tie-break rule applies.
- **Observation.** The same attack paragraph appears in 3 of the 6 Portuguese
  `prompt_injection` cases, so the exam measures resistance to one phrasing
  more than to the attack type.
- **Takeaway.** Templates make authoring fast and quietly make cases look
  alike; a similarity check over the dataset shows where the template, not the
  scenario, is doing the talking.

## 2026-11-07 · Step 3 · A new persona is not a new case

- **Expected.** Varying the customer profile (formal, slang, low digital
  literacy, detail-oriented…) across typical cases would make them different
  cases.
- **What happened.** Reviewing the semantic warnings, three pairs turned out
  to be the same scenario in another voice: installment plan billed wrong
  (`payment-009` formal × `payment-018` low literacy), cancel before shipping
  by choice (`cancellation-001` × `cancellation-009`), screen defect found on
  unboxing (`return_refund-001` × `return_refund-012`). Each pair counts one
  scenario twice in the exam.
- **Why.** The authoring guide asks for varied profiles *across* scenarios;
  writing them as variations *of* one scenario is what the plan calls an
  invariance test, a separate future suite generated by code.
- **Decided.** Luis's criterion: same operational mechanics = same scenario,
  whatever the product, reason or tone. One case of each pair is rewritten
  with a trigger the category does not have yet (the matrix forbids removing
  cases); the "assunto" pairs keep both cases with the difference recorded in
  `notes`.
- **Takeaway.** Diversity of wording is not diversity of behaviour. Define
  "different case" by what the system must do differently, then check the
  dataset against that definition.

## 2026-11-07 · Step 3 · The audit found a gap in the rules, not in the labels

- **What happened.** The LLM label audit (3 prompt variants, 140 cases,
  US$ 0.52) confirmed 138 labels, flagged 1 and had no consensus on 1. The
  flag, `general-002` ("where do I save my address in the app?"), was
  `account` for all 3 variants; Luis's blind answer was `general`, the
  original label. The no-consensus case, `general-018` ("how do I open an
  account?"), had the same shape.
- **Why.** Both are "how-to about the account". The models read the subject
  (account data); the master rule asks for the request (an explanation). No
  tie-break rule covered `general` × `account`.
- **Decided.** Label kept; new tie-break rule `general` × `account` added to
  the taxonomy before classifier prompt v1 is written (§12).
- **Takeaway.** When independent prompts agree against a careful human, the
  disagreement often points at an ambiguous rule rather than a wrong label.
  Fix the rule at its source, while it is still cheap.

## 2026-11-17 · Step 4 · Copying the files changed the identity of the prompt

- **Expected.** Files pasted from the chat would be the same as the tested
  copy, since the content was the same.
- **What happened.** 17 of the 20 files lost their final newline when pasted,
  and the `config/taxonomy/v1.md` fix left a last line holding only two
  spaces. All 140 tests and `ruff check` passed, yet
  `prompts/classifier/v1.yaml` hashed to `4ed7157b1f97` instead of the tested
  `ef228ba56ace`. Only a byte-by-byte comparison with the tested copy, and
  then `ruff format --check` (17 files), showed it.
- **Why.** The prompt's identity is the sha256 of its bytes (decision 1.3),
  so an invisible newline makes it a different version. The lint rules in
  use do not include the final-newline check, and the tests read the
  content, not the bytes.
- **Decided.** Fixed before the merge, while v1 was still unpublished
  (`ruff format`, final newline on the YAML files, stray line removed).
  Before each commit the agent compares the placed files with the tested
  copy and the sha256 of any prompt file; `ruff format --check` is part of
  every step's checks (§12).
- **Takeaway.** When identity is a hash, the check has to read bytes too: "the
  tests pass" and "it looks the same" say nothing about a file's
  fingerprint. Check the identity before it becomes immutable.

## 2026-11-16 · Step 4 · A guide that said more than its decision

- **What happened.** Wiring the few-shot overlap check, the validation guide
  said any overlap between a prompt example and a golden case **blocks**,
  while decision 2.6 applies its rules per layer (exact and lexical ≥ 90
  block; similar and semantic only warn). Following the guide, every
  semantic neighbour of the same topic would have blocked v1, although
  embeddings measure the topic, not the request (step 3 lesson).
- **Decided.** The decision wins; the guide was corrected (§12, few-shot
  overlap severities). The v1 examples then had no overlap flag at all
  (highest lexical score 61).
- **Takeaway.** A guide is a summary of a decision and drifts from it
  silently. When code implements a rule, read the decision, not only the
  guide.

## 2026-11-17 · Step 5 · A fake kinder than the real adapter

- **Expected.** Cache tests with a fake client covering every status would
  prove that only `completed` calls are stored.
- **What happened.** Before delivering the code, the status check was
  removed on purpose to see a test fail. All 190 tests stayed green. The
  fake returned no text for `invalid_output` and `incomplete`, while the
  real `OpenAIClient` keeps the broken text the model wrote; and the cache
  re-validates the text on read, which hid the rest.
- **Why.** The fake was built from the list of statuses, not from what the
  adapter actually returns for each one; and with two layers of defence,
  an end-to-end test cannot see either layer alone.
- **Decided.** The fake returns broken text for those two statuses, like
  the adapter, and the test reads the cache table directly. Both deliberate
  breaks (no concurrency limit; storing non-completed calls) now fail
  tests.
- **Takeaway.** A fake must reproduce the real adapter's outputs, not a
  tidy version of them; and a test must be seen failing against the break
  it claims to catch: the step 3 rule for thresholds, applied to tests.

## 2026-11-17 · Step 5 · Pasted code, checked by hash again

- **Expected.** With the step 4 lesson known, the 16 files pasted from the
  chat would match the tested copy.
- **What happened.** Two pasted files lost their final newline again, and
  one test file was pasted twice under two names
  (`test_client_cache.py` and `test_caching_client.py`), the first copy
  from an older version of the file. The import error and the sha256
  comparison caught both before the commit.
- **Why.** The editor does not add a final newline on save, and the step
  delivered one file in two versions (the SQLite version check was removed
  after the first delivery).
- **Decided.** The editor inserts a final newline on save; a file that
  changes after delivery is sent again in full with a note naming the
  version to use; the expected test count is given with the commands, so
  a duplicate shows up as a wrong total.
- **Takeaway.** Copying by hand is the chosen workflow (it keeps the code
  read line by line), so the byte check stays a fixed step before every
  commit.

## 2026-11-17 · Step 6 · The final newline, a third time

- **Expected.** With the editor setting suggested in step 5, pasted files
  would keep their final newline.
- **What happened.** Seven pasted files lost it again; `ruff format
  --check` flagged them, and the byte check showed it was the only
  difference.
- **Why.** The editor setting was not in place, and the check only reports
  the problem instead of fixing it.
- **Decided.** The formatter has no option to drop the final newline, and
  dropping the check would move the failure to CI (step 14). The routine now
  starts with `uv run ruff format src tests`, which adds it; the editor
  setting covers YAML and Markdown, which ruff does not touch.
- **Takeaway.** When a manual step keeps failing the same way, make the
  tool fix it rather than report it, and keep the byte check as the proof.

## See also

- Decisions with dates and reasons: [`planning.md` §12](planning.md#12-decisions)
- Build order, open items and status: [`implementation-plan.md`](implementation-plan.md)
