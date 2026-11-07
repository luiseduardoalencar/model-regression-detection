# Model Regression Detection

A quality gate for a non-deterministic LLM feature. A golden dataset, a
classification scorer and an LLM judge measure every prompt or model change
against the current baseline when a PR is opened. Critical regressions block
the merge. Alerts go to Telegram with an HTML report attached. There are no
scheduled runs: the gate is an extra validation layer at PR time.

The feature under test is a customer support email classifier for a fictional
Brazilian marketplace. It reads an email in Portuguese and returns one of 7
categories plus a one-sentence summary. It is never deployed to production.

**Status:** all planning decisions closed (Phases 1–6); the
[implementation plan](docs/implementation-plan.md) (18 build steps) was
approved on 2026-11-05. Steps 1 and 2 are done (2026-11-06): domain models,
the golden file schema and offline validation of the golden draft; the LLM
port, the OpenAI adapter and cost per call from `config/pricing.yaml`. There
is no classifier or evaluation code yet.

## Quick start

```bash
uv sync          # Python 3.12, dependencies from uv.lock
uv run pytest    # unit tests (tests marked `live` are skipped)
uv run validate-golden   # validate the golden draft and list its flags
uv run --env-file .env pytest -m live -s   # one real OpenAI call; spends money
uv run ruff check .
cp .env.example .env   # fill in secrets locally; never commit .env
```

## Documentation map

| Document | What it holds |
|---|---|
| [`docs/planning.md`](docs/planning.md) | **Source of truth**: goal, stack, data, architecture, build plan with checklists, and the dated decisions log (§12) |
| [`docs/implementation-plan.md`](docs/implementation-plan.md) | Approved build order (steps 1–18): what each step builds and enables, manual work, mapping to the §7 checklist, open items and status |
| [`docs/foundations.md`](docs/foundations.md) | Concepts and choices made before the phases: project nature, models, generation parameters, market tools, architecture, naming |
| [`docs/phases/`](docs/phases/) | One document per phase, with every sub-step's decision, its rationale and its references |
| [`docs/guides/`](docs/guides/) | Step-by-step procedures for the manual work (writing golden cases, label checks, judge calibration, prompt changes, setup) |
| [`docs/agent-prompts/`](docs/agent-prompts/) | Ready-to-paste prompts for an AI agent (e.g. in Cursor): manual work, and [`implementation-plan-session.md`](docs/agent-prompts/implementation-plan-session.md) to start the build |
| [`docs/summary-guide.md`](docs/summary-guide.md) | The rules a correct summary follows (used by the golden set, the prompt and the judge) |
| [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md) | Entry point and rules for AI agents working on this project (`AGENTS.md` points to `CLAUDE.md`) |

### Phases

1. [Feature under test](docs/phases/phase-1-feature.md)
2. [Golden dataset](docs/phases/phase-2-golden-dataset.md)
3. [Evaluation engine](docs/phases/phase-3-evaluation-engine.md)
4. [Reporting and alerting](docs/phases/phase-4-reporting-alerting.md)
5. [CI/CD](docs/phases/phase-5-ci-cd.md)
6. [Portfolio polish](docs/phases/phase-6-portfolio.md)

## Stack (decided)

Python 3.12 with uv · OpenAI Responses API (`gpt-6-luna` for the feature,
`gpt-6.1-terra` for the judge) · DeepEval G-Eval · scikit-learn metrics ·
Langfuse self-hosted locally · SQLite · Telegram Bot API · GitHub Actions ·
Docker (local runs only).
Details and reasons are in [`docs/foundations.md`](docs/foundations.md).
