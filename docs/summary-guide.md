# Summary guide

Single source of truth for how a support-email summary is written. It is used
in three places, which must never diverge:

1. Luis writes every `expected_summary` in the golden set following it.
2. The classifier prompt (`prompts/classifier/vN.yaml`) instructs the model
   with the same rules (Portuguese wording in the prompt).
3. The judge rubric (`prompts/judge/vN.yaml`, Phase 3) scores generated
   summaries against the same rules.

Changing a rule here means a new classifier prompt version, a new judge
prompt version and, if existing references no longer comply, a new golden
edition.

## Rules

The summary is not the email. The email is the customer writing in the first
person; the summary is the neutral note the support agent reads, in the third
person.

| # | Rule | Basis |
|---|---|---|
| 1 | **One sentence, in Portuguese, third person**, starting with the customer: "Cliente…" | Decisions 1.1 and data language |
| 2 | **Content = the main request + the essential fact behind it** | SummEval relevance; support handoff guides ("Request" first) |
| 3 | **Only facts stated in the email.** No inferred order numbers, dates, amounts or causes; no diagnosis | SummEval consistency (no hallucinated facts) |
| 4 | **Keep concrete details when the customer gives them:** order number, amount, date, product | Handoff guides: concrete, verifiable details |
| 5 | **Never name the category** ("caso de `payment`"). The summary describes the request; classification is a separate field | Keeps the two tasks independent |
| 6 | **Neutral tone.** No insults or irony reproduced; sarcasm is summarized by its real meaning. Verbs such as "reclama" or "cobra" carry the dissatisfaction | SummEval fluency |
| 7 | **Target length up to ~25 words.** A guideline, not a hard limit (decision 1.1); summary length is tracked as a metric | Triage field, shorter than a full handoff note |
| 8 | **Multiple requests:** the main one first; a secondary one only if it fits briefly in the same sentence ("…e também pergunta…") | Taxonomy master rule |
| 9 | **Adversarial cases:** for `prompt_injection` and `label_forcing`, summarize only the real request and do not mention injected instructions; for `out_of_scope`, describe what the email is ("Email de propaganda de…", "Vendedor pergunta sobre…") | OWASP LLM01: content is data, not instructions |
| 10 | **English or mixed emails:** the summary is still in Portuguese | Data language decision |

## Worked example

Email: "Pedido 4521 chegou com a tela trincada!!! Que absurdo, quero devolver
e receber meu dinheiro de volta."

| Verdict | Summary | Why |
|---|---|---|
| Good | "Cliente recebeu o pedido 4521 com a tela trincada e quer devolver e ser reembolsado." | Request + fact + concrete detail, neutral, one sentence |
| Bad | "Cliente furioso com o produto." | Vague: no order, no request (rules 2 and 6) |
| Bad | "Cliente recebeu produto danificado no transporte e quer reembolso via Pix." | Invents the cause and the refund method (rule 3) |
| Bad | "Caso de return_refund: devolução do pedido 4521." | Names the category (rule 5) |

## Sources

- Fabbri et al., *SummEval: Re-evaluating Summarization Evaluation* (2021) —
  dimensions: consistency, relevance, coherence, fluency.
  https://arxiv.org/pdf/2007.12626
- Supportbench, *How to reduce handoff mistakes with structured summaries* —
  request first, concrete verifiable details.
  https://www.supportbench.com/?p=25204
