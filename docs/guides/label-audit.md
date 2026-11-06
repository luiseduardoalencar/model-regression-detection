# Guide — Resolving the LLM label audit

**Used in:** Phase 2 (decision 2.5a), after all cases of the edition are
written and validated, before the intra-annotator check.

## What the audit does (automatic)

`gpt-6.1-terra`, with 3 different prompt variants, labels every case using the
taxonomy only. A case is **flagged** when the 3 variants agree with each
other and disagree with Luis's `expected_category` (and the predicted label is
not in `acceptable_categories`). The LLM never writes a label.

## Procedure for each flagged case

1. Show **only the email** and ask Luis: "Para qual fila esse email vai?"
   (no labels shown yet — avoid anchoring).
2. Then show: Luis's original label, the label he just gave, the audit label
   and the audit's short justification.
3. Luis decides one of:
   - **Keep** the original label (the audit is wrong).
   - **Relabel** the case.
   - **Add** the audit label to `acceptable_categories` (genuinely ambiguous).
   - **Rewrite** the email so the intended category is defensible.
4. Record the decision in `notes`, in Portuguese:
   `Auditoria <data>: <mantido | trocado de X para Y | aceitável Y | reescrito> — <motivo>.`
5. If several flags point to the same tie-break rule, tell Luis: the rule may
   be unclear and the taxonomy may need a fix (a documentation change, see
   the project `CLAUDE.md`).

## Done when

Every flagged case has a recorded decision. The header of the edition records
the audit date.

## References

1. Northcutt et al., *Pervasive Label Errors in Test Sets Destabilize ML Benchmarks* — https://arxiv.org/abs/2103.14749
2. *Are LLMs Better than Reported? Detecting Label Errors* (arXiv 2410.18889) — https://arxiv.org/html/2410.18889v2
