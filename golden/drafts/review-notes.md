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

## Semantic review (2026-11-07, build step 3)

`uv run --env-file .env validate-golden` with the semantic layer
(`text-embedding-3-large`, threshold 0.74): 27 warnings, 0 blocking
(5 label conflicts, 22 semantic pairs). Criterion decided by Luis: **same
operational mechanics = same scenario**, whatever the product, the reason or
the customer profile (`docs/planning.md` §12).

- [x] **Label conflicts** — all labels kept, difference recorded in `notes`:
      `return_refund-008` × `payment-008` (same attack paragraph),
      `delivery-009` × `cancellation-004` / `cancellation-011`,
      `delivery-021` × `cancellation-011`, `cancellation-005` ×
      `return_refund-005` (same persona). These are minimal pairs on purpose.
- [x] **Different scenario, same subject** — kept, `notes` updated:
      `delivery-009` × `delivery-021`, `payment-001` × `payment-009`,
      `delivery-003` × `delivery-018`.
- [x] **Same scenario** — rewrite one case of each with a trigger the category
      does not have yet (same cell: typical, difficulty, language, profile):
  - [x] `payment-018` (kept `payment-009`): payment split across two cards,
        one declined, order stuck (rewritten 2026-11-07).
  - [x] `return_refund-012` (kept `return_refund-001`): defect after weeks of
        use, under warranty, asks for a replacement (rewritten 2026-11-07).
  - [x] `cancellation` "cancel before shipping by choice" was 7 of 14 typical
        cases; kept `cancellation-001` (formal) and `cancellation-002`
        (slang); rewrote (2026-11-07, emails and summaries by Luis, cell
        unchanged) `cancellation-009` (already shipped, in transit),
        `cancellation-014` (purchase made by mistake by a child),
        `cancellation-020` (wrong delivery address, cancel and redo),
        `cancellation-018` (boleto generated and not paid, cancel formally),
        `cancellation-010` (forgot the coupon, cancel and redo; PT + EN).
        Summaries aligned to the "do pedido N" style of the other cases.
  - First drafts of `payment-018` (Pix discount not applied) and
    `return_refund-012` (defect found on first use) repeated `payment-012`
    and `return_refund-001`; replaced by the versions above.
- [x] **Second semantic run (2026-11-07)** — 23 warnings, 0 blocking; pairs
      A–H judged "same subject", `notes` updated (`cancellation-001` ×
      `-009`, `delivery-008` × `cancellation-020`, `cancellation-004` ×
      `-011` / `-019`, `payment-001` × `-011` / `-010`, `payment-009` ×
      `-016`, `delivery-008` × `-020`).
- [ ] **Parked until before the freeze (step 10)** — applying the criterion to
      the whole of `account` and `payment` (proposal of 2026-11-07, not yet
      confirmed by Luis): `account` password group (`002`, `003`, `006`,
      `007`) and profile change `005`; `payment` duplicate charge (`003`,
      `013`, `014`), card declined `006`, overcharge `012`. Does not block
      step 3 or the build; only the freeze needs a decision.
- [ ] ~~Still to review~~ (superseded by the second run above) — `cancellation-004` × `-011` / `-019` / `-009`
      (delay then cancel), `payment-001` × `-011` / `-010`, `payment-009` ×
      `-016`, `delivery-008` × `-020`, `account-002` × `-006`. Re-run the
      validation after the rewrites first: some pairs will change.

## LLM label audit (2026-11-07, build step 3)

`uv run --env-file .env audit-labels` (`gpt-6.1-terra`, 3 variants, 420
calls, US$ 0.52): 138 confirmed, 1 flagged, 1 no consensus, 0 not audited.
Details in `label-audit.json` (opened by the agent, after Luis's blind
answer).

- [x] `general-002` — flagged (audit: `account`); Luis's blind answer
      `general`, same as the label: kept, reason in `notes`. Led to the new
      tie-break rule `general` × `account` in `config/taxonomy/v1.md`.
- `general-018` — no consensus (not a flag; 2 `general`, 1 `account`): same
  "how-to about the account" pattern, now covered by the new rule.

Observation for a future edition: the same prompt-injection paragraph appears
in 3 of the 6 Portuguese `prompt_injection` cases.

## Not checked yet (need code)

- LLM label audit — guide [`label-audit.md`](../../docs/guides/label-audit.md).
- Intra-annotator check (20 blind re-labels, kappa ≥ 0.7) — guide
  [`intra-annotator-check.md`](../../docs/guides/intra-annotator-check.md).
