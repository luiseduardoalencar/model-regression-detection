# Guide — Intra-annotator check (blind re-labeling)

**Used in:** Phase 2 (decision 2.5b), at least a few days after the label
audit, as the last step before freezing the edition.

## Procedure

1. Sample **20 cases at random** from the draft edition (fixed random seed,
   recorded in the edition header).
2. Show Luis **only the email** of each case, one at a time — no ID, no
   notes, no previous label. Ask: "Para qual fila esse email vai?"
3. Record his answer; do not comment or reveal the original label until all
   20 are done.
4. Compute **Cohen's kappa** between the original labels and the new ones
   (scikit-learn `cohen_kappa_score`), plus the raw agreement.
5. Show the result and the disagreements.

## How to read the result

- **Cohen's kappa** measures agreement beyond chance: 1 = perfect, 0 = no
  better than chance.
- **kappa ≥ 0.7:** labels are consistent; the edition can be frozen (if
  validation and the audit are also done).
- **kappa < 0.7:** the problem is most likely the guidance, not Luis. Look at
  which tie-break rules the disagreements involve, revise the taxonomy
  definitions or rules (documentation change), relabel the affected cases and
  repeat the check with a new sample.

## Done when

kappa ≥ 0.7. The result (kappa, agreement, seed, date) is recorded in the
edition header.

## References

1. scikit-learn — `cohen_kappa_score` — https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html
2. *Are LLMs Better than Reported? Detecting Label Errors* (annotation consistency) — https://arxiv.org/html/2410.18889v2
