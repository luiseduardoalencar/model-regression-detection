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

## See also

- Decisions with dates and reasons: [`planning.md` §12](planning.md#12-decisions)
- Build order, open items and status: [`implementation-plan.md`](implementation-plan.md)
