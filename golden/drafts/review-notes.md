# Golden edition 1 — review notes (draft)

Review of `golden/drafts/edition-1.json` on 2026-11-04 (140 cases). Each item
is resolved by Luis with the agent prompt
[`docs/agent-prompts/golden-review-agent.md`](../../docs/agent-prompts/golden-review-agent.md);
mark it `[x]` and write the decision next to it.

## Must fix before freezing (coverage matrix, decision 2.1)

- [x] **R1 — `delivery` had 15 `typical` and 3 `edge` (target 14 / 4).**
      Removed `delivery-013` (ID retired, never reused). Added `delivery-021`:
      edge, `ambiguous` + `multiple_requests`, `hard`,
      `acceptable_categories: ["cancellation"]`. Main action is locating the
      drill on order 43902; cancelling the unshipped screwdriver is a second
      current request.
- [x] **R2 — 33 `hard` cases (target ≥ 35).** R1 added one `hard` case.
      Rewrote `payment-003` to "Pix pedido 9033 saiu dobrado." Still
      `very_short` (five words); difficulty is now `hard`. Hard count is 35.

## Worth reviewing (Luis decides; keeping is a valid answer)

- [x] **R3 — `payment-015` (`label_forcing`).** Forced label in the email
      changed from `account` to `technical`. The summary stays on the
      unrecognised charge. `technical` is not in `acceptable_categories`.
- [x] **R4 — `delivery-011` summary.** Now "Cliente informa que o seu pacote
      73910 sumiu." The number is not called an order.
- [x] **R5 — `delivery-004` summary.** "ele" replaced with "destinatário".
      "ontem" and the doorman stay in the summary.

## Checked and OK

- 20 cases per category; 14 adversarial (2 per category: `prompt_injection`
  + `label_forcing`; `general`: 2 `out_of_scope`).
- 14 English/mixed cases (2 per category).
- Every edge type appears at least twice among the edge cases.
- IDs unique; all fields present.
- No exact duplicates; highest lexical similarity between two emails
  (`token_sort_ratio`) is 66, below the 80 warning threshold (quick check, not
  the official validation script).
- Summaries start with "Cliente" except the two `out_of_scope` cases (allowed
  by summary rule 9); no category label inside a summary; mean length 21.6
  words. After R1–R2: every category is 14 typical / 4 edge / 2 adversarial,
  and there are 35 `hard` cases.

## Second check (2026-11-04, after R1–R5)

All structural targets met: 14 / 4 / 2 per category, 35 `hard`, 14
English/mixed, every edge type ≥ 2, schema and IDs valid, highest lexical
similarity 66. Watch item for the semantic duplicate check (not a blocker):
the duplicate-charge scenario appears in 6 of 20 `payment` cases (`payment-001`,
`-003`, `-008`, `-011`, `-013`, `-014`) and passwords in 8 of 20 `account`
cases; if the embeddings check flags pairs among them, vary the scenario.

## Validation script (2026-11-06)

`uv run validate-golden` (build step 1) on this draft: 0 flags. It confirms
the structural targets above and finds no exact duplicates and no lexical
pairs at or above 80.

## Not checked yet (need code)

- Semantic duplicates (embeddings) — validation script, guide
  [`validation-flags.md`](../../docs/guides/validation-flags.md).
- LLM label audit — guide [`label-audit.md`](../../docs/guides/label-audit.md).
- Intra-annotator check (20 blind re-labels, kappa ≥ 0.7) — guide
  [`intra-annotator-check.md`](../../docs/guides/intra-annotator-check.md).
