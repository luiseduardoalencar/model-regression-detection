# Guide — Writing the golden set cases

**Used in:** Phase 2 (decisions 2.1–2.4). **Agent prompt:**
[`../agent-prompts/golden-authoring-agent.md`](../agent-prompts/golden-authoring-agent.md). **Output:** the draft file
`golden/drafts/edition-1.json`, frozen later as `golden/edition-1.json`
(see [`label-audit.md`](label-audit.md) and
[`intra-annotator-check.md`](intra-annotator-check.md) for the freeze criteria).

## Roles

| Luis | Agent |
|---|---|
| Types the email in his own words (Portuguese, or English/mixed when the brief says so) | Chooses the next case from the coverage tracker and sends the brief, including one example email for inspiration |
| Writes the expected summary | Structures the JSON case and assigns the ID |
| Confirms or changes the category, `acceptable_categories` and difficulty | Checks the summary against the summary guide and points out issues (never rewrites it) |
| Approves the `notes` | Drafts `notes` from the brief; keeps the tracker up to date |

The agent's example email is inspiration only: Luis types his own version, and
that is what goes into the dataset. The agent never writes the expected
summary and never decides a label.

The email is the customer writing to the marketplace, in the first person and
in the customer's own voice. The expected summary is the one-sentence note
the support agent sees, in the third person, starting with "Cliente…". The
"Cliente" rule applies only to the summary.

## Sources the agent must read first

- Taxonomy, master rule and tie-break rules — [`../planning.md` §4](../planning.md#category-taxonomy)
- Coverage matrix, edge/adversarial types, difficulty rubric — [`../planning.md` §4](../planning.md#golden-file)
- Summary rules — [`../summary-guide.md`](../summary-guide.md)
- Case fields — [`../planning.md` §4](../planning.md#golden-file)

## Coverage tracker

Before each brief, the agent computes what is still missing:

| Target | Rule |
|---|---|
| Per category | 14 `typical` + 4 `edge` + 2 `adversarial` = 20 |
| Edge types | Each of the 10 types at least twice among the 28 `edge` cases; `ambiguous`, `temporal`, `negation` on the hard boundaries |
| Adversarial | Two per category (`prompt_injection` or `label_forcing`); `general` gets two `out_of_scope` |
| Language | ~14 English or mixed cases spread across case types |
| Difficulty | At least 35 `hard` |
| Customer profiles (typical cases) | Vary: formal, informal with slang, angry, low digital literacy, in a hurry (short but clear), detail-oriented |

Order of work: go category by category, mixing case types inside each
category, so that each category is complete before moving on.

## Procedure for one case

1. **Pick the cell** (category, case type, edge types, language, target
   difficulty, customer profile) from the tracker.
2. **Send the brief in Portuguese**, using the template below. Give the
   category definition and, when relevant, the tie-break rule being tested,
   plus one example email showing how it could look.
3. **Luis writes** the email and the expected summary.
4. **Check the summary** against the 10 rules of the summary guide. If a rule
   is broken, say which rule and why; Luis rewrites it.
5. **Structure the JSON case** (template below):
   - `id` = `<category>-<NNN>`, zero-padded, never reused (e.g.
     `delivery-007`).
   - `case_type`, `edge_types`, `language` from the brief and the text.
   - `expected_category` from the brief; `expected_difficulty` suggested
     from the rubric.
   - `notes` drafted in Portuguese: why the case exists.
6. **Show the case back** and ask Luis to confirm: category, whether
   `acceptable_categories` applies, difficulty, notes. Apply his answer.
7. **Append** to `golden/drafts/edition-1.json`, update the tracker, report
   progress ("caso 37 de 140").
8. When the validation script exists, run it after each batch of ~10 cases
   and handle flags with [`validation-flags.md`](validation-flags.md).

## Brief template (sent in Portuguese)

```
Caso <id previsto> · <n> de 140
Categoria pretendida: <label> — <definição de uma frase>
Tipo de caso: <typical | edge | adversarial>  ·  Tipos de borda: <lista ou "nenhum">
Regra testada: <regra de desempate, se houver>
Perfil do cliente: <perfil>  ·  Tom: <tom>  ·  Tamanho: <curto | médio | longo>
Idioma: <pt | en | mixed>  ·  Dificuldade alvo: <easy | medium | hard>
Cenário: <uma ou duas frases descrevendo a situação>
Exemplo de email (só inspiração; escreva a sua versão): "<exemplo curto>"
Escreva: o email e o resumo esperado (uma frase, regras do guia de resumo).
```

## Case template (JSON)

```json
{
  "id": "delivery-007",
  "input_email": "<written by Luis>",
  "expected_category": "delivery",
  "acceptable_categories": [],
  "expected_summary": "<written by Luis>",
  "expected_difficulty": "medium",
  "case_type": "typical",
  "language": "pt",
  "edge_types": [],
  "notes": "<drafted by the agent, approved by Luis>"
}
```

## Common mistakes the agent must catch

- The email was written to "fit" the category too neatly for a `hard` case —
  ask whether an attentive agent would really hesitate.
- The summary names the category, invents a fact, or drops the order number
  the customer gave.
- An adversarial email whose real request is unclear — the real request must
  be identifiable, otherwise the expected answer is not defensible.
- Two cases describing the same scenario with different words — flag it now
  rather than waiting for the semantic duplicate check. Same scenario = same
  operational mechanics (what the support team must recognise and do),
  whatever the product, the reason given or the customer profile (decided
  2026-11-07). Profiles vary across scenarios, never within one scenario;
  the same scenario in several voices is an invariance test, a separate
  future suite.

## References

1. Apple — Designing datasets to test your feature — https://developer.apple.com/documentation/evaluations/designing-evaluation-datasets
2. FutureAGI — LLM Eval Golden Set Design: A 2026 Engineering Guide — https://futureagi.com/blog/llm-eval-golden-set-design-2026/
3. Hamel Husain — Generate synthetic data (dimensions and tuples for briefs) — https://skills.sh/hamelsmu/evals-skills/generate-synthetic-data
4. Ribeiro et al., *CheckList* (ACL 2020) — https://homes.cs.washington.edu/%7Emarcotcr/acl20_checklist.pdf
5. OWASP Top 10 for LLM Applications 2025 (LLM01 prompt injection) — https://dev.to/kuboidsecurelayer/owasp-top-10-for-llm-applications-2025-plain-english-explanation-with-real-examples-2i7f
6. CLINC OOS (out-of-scope cases) — https://www.tensorflow.org/datasets/catalog/clinc_oos
7. Supportbench — Structured summaries for handoffs — https://www.supportbench.com/?p=25204
