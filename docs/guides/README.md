# Guides for manual steps

Step-by-step procedures for every task that needs Luis's work. They are
written so that **any agent** can guide Luis through the task correctly.
The agent always talks to Luis in Portuguese; files stay in English (data in
Portuguese where the decisions say so).

| Guide | When it is used | Phase |
|---|---|---|
| [`initial-setup.md`](initial-setup.md) | One-time setup: local Langfuse, Telegram bot, GitHub secrets, required `eval` check on `main`, OpenAI spend limit; optional Docker run | 1 / 5 |
| [`golden-case-authoring.md`](golden-case-authoring.md) | Writing the golden set cases, one brief at a time | 2 |
| [`validation-flags.md`](validation-flags.md) | Resolving flags from the golden validation script (duplicates, label conflicts, matrix gaps) | 2 |
| [`label-audit.md`](label-audit.md) | Resolving cases flagged by the LLM label audit | 2 |
| [`intra-annotator-check.md`](intra-annotator-check.md) | Blind re-labeling of 20 cases and Cohen's kappa | 2 |
| [`judge-calibration.md`](judge-calibration.md) | Judging 100 generated summaries to calibrate the LLM judge | 3 |
| [`prompt-change.md`](prompt-change.md) | Reviewing classifier prompt v1, creating any new prompt version, and running the proof scenarios | 1, 6 and ongoing |

Ready-to-paste agent prompts built on these guides:
[`../agent-prompts/golden-authoring-agent.md`](../agent-prompts/golden-authoring-agent.md),
[`../agent-prompts/golden-review-agent.md`](../agent-prompts/golden-review-agent.md)
and [`../agent-prompts/judge-calibration-agent.md`](../agent-prompts/judge-calibration-agent.md).

## Rules every agent follows in these guides

1. **Luis types the golden content:** the agent may show an example email
   in the brief for inspiration, but Luis types the email himself, writes
   the expected summary and decides the labels. The agent prepares briefs,
   structures JSON, runs checks and points out problems.
2. **No anchoring:** when Luis must judge something (a label, a summary),
   the agent asks for his answer **before** showing any model output or its
   own opinion.
3. **One item at a time**, with the current progress (e.g. "caso 37 de 140").
4. **Record decisions where the guide says** (usually the case `notes`) and
   keep the documentation in sync (see the project `CLAUDE.md`).
5. **Never invent rules.** Taxonomy, tie-break rules, edge types, difficulty
   rubric and summary rules come only from
   [`../planning.md` §4](../planning.md#4-data) and
   [`../summary-guide.md`](../summary-guide.md).
