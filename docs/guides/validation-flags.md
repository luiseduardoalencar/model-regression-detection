# Guide — Resolving golden validation flags

**Used in:** Phase 2 (decisions 2.1–2.3, 2.6, 1.4), whenever the validation
script reports something about the golden draft or the few-shot examples.

## Flag types and what to do

| Flag | Severity | What the agent shows Luis | Possible resolutions |
|---|---|---|---|
| Schema / enum error | Blocks | The case and the invalid field | Fix the field |
| Exact duplicate | Blocks | Both cases side by side | Delete one, or rewrite one into a different scenario |
| Lexical near-duplicate (`token_sort_ratio` ≥ 90) | Blocks | Both cases and the score | Rewrite one so the scenario differs, or delete one |
| Lexical warning (80–90) | Warns | Both cases and the score | Keep (explain the difference in `notes`) or rewrite |
| Semantic warning (cosine ≥ 0.74) | Warns | Both cases and the score | Same as above: is it really the same scenario? |
| **Label conflict** (similar pair, different `expected_category`) | Highest priority (listed first; the pair's duplicate flag decides whether it blocks) | Both cases, both labels, the tie-break rule involved | Fix one label; or add `acceptable_categories`; or make the difference explicit in both texts and `notes` |
| Few-shot overlap (a prompt example similar to a golden case) | Blocks | The example and the case | Change the **few-shot example** (the golden case stays) |
| Matrix gap (exact targets: counts per category / case type, each edge type ≥ 2, adversarial subtypes, ≥ 35 `hard`) | Blocks freezing | The missing cells | Write the missing cases with [`golden-case-authoring.md`](golden-case-authoring.md) |

Approximate targets (~10 % English/mixed per case type, the difficulty mix
per case type) are printed as information, never as flags; nothing to
resolve (decided 2026-11-05).

Implementation status (2026-11-06): `uv run validate-golden` reports schema
errors, exact and lexical duplicates, label conflicts, matrix gaps and
edge-type rule flags (an edge case with no type, an adversarial case without
its allowed subtype, an adversarial type on a non-adversarial case). Build
step 3 (2026-11-07) adds the semantic warning (`semantic_pair`, model in
`config/embeddings.yaml`); a pair already caught by the lexical layer is not
repeated. Without `OPENAI_API_KEY`, or when the API stays unavailable after
its retries, the command prints "semantic layer skipped: <reason>" and goes
on: the layer only warns, so skipping it never hides a blocking flag. The
few-shot overlap flag arrives in step 4.

## Procedure

1. Show flags grouped by severity: label conflicts first, then blocking
   flags, then warnings.
2. For each flag, ask Luis for a decision **before** suggesting one.
3. Apply the decision and record the reason in the case `notes`
   (e.g. "Revisado na validação: cenário diferente de delivery-004, aqui o
   pedido já foi enviado").
4. Re-run the script until no blocking flag remains.

Thresholds are never changed to make a flag disappear; they are calibrated
only with the unit-test fixture (decision 2.6).

## References

1. RapidFuzz — fuzzy matching functions (`token_sort_ratio`) — https://tessl.io/registry/tessl/pypi-rapidfuzz/3.14.0/files/docs/fuzzy-matching.md
2. eval-toolkit — Text deduplication methodology — https://brandon-behring.github.io/eval-toolkit/methodology/text_dedup.html
3. ZeroEntropy — Deduplication — https://www.zeroentropy.dev/concepts/deduplication/
4. Northcutt et al., *Pervasive Label Errors in Test Sets* (label conflicts matter) — https://arxiv.org/abs/2103.14749
