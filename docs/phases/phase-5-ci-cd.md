# Phase 5 — CI/CD

**Goal:** make the evaluation mandatory and reproducible — a GitHub Actions
gate on every PR that changes prompts or the gate configuration, and a
Dockerfile that runs the same eval locally without installing Python or uv.

**Status:** decisions closed (5.1–5.3, 2026-11-04). Not implemented yet.
Implementation checklist: [`planning.md` §7, Phase 5](../planning.md#phase-5--cicd).

## Already fixed before this phase

- PR trigger only; no scheduled runs (decided 2026-11-04,
  [`foundations.md`](../foundations.md) F1).
- Nothing is deployed or published; the Docker image is not published.
- CI secrets: `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  (GitHub Secrets only; never printed).
- CI uses `NoopTracer` (GitHub runners cannot reach the local Langfuse).
- The baseline is re-run in each PR job (3.6); no stored baseline is needed
  for the gate.
- A CI check fails if a published prompt version is edited (1.3); the
  duplicate and few-shot overlap checks run whenever `prompts/` or `golden/`
  change (1.4, 2.6).

## 5.1 Triggers

**Decision (2026-11-04).**

1. **Eval-relevant paths** (decided inside the job, see point 2):

   | Path | Runs the eval? | Why |
   |---|---|---|
   | `prompts/**` (classifier, judge, `active.yaml`) | Yes | What the gate exists to measure |
   | `config/gate.yaml` (new: thresholds 5 / 7, absolute floor, golden edition in use) | Yes | Changing a threshold, the floor or the edition changes the verdict; the PR that sets the floor after the first v1 run is itself measured |
   | `.github/workflows/eval.yml` | Yes | A change to the gate is tested by the gate |
   | `golden/**` | No | Validated by `checks.yml` (2.6); switching the edition used by the gate goes through `config/gate.yaml` |
   | `src/**` | No | Both sides run the PR's code (3.6), so the paired comparison cannot see a code change; unit tests cover it |
   | `config/pricing.yaml` | No | Only changes the reported cost; unit tests cover it |

   When `config/gate.yaml` changes, the report header shows "gate config
   changed in this PR", so a PR cannot loosen its own thresholds unnoticed.
2. **No workflow-level `paths` filter.** `eval.yml` runs on every PR to
   `main`; its first step lists the files of the whole PR against `main`
   (`git diff --name-only`) and calls `is_eval_relevant(paths)` (Python,
   unit-tested). If nothing relevant changed, the job succeeds with "eval
   skipped: no eval-relevant changes": no API calls, no Telegram, no comment.
   Because the whole PR is compared, a later push that only touches `src/`
   on a PR that already changed a prompt still runs the eval.
3. **Cheap checks on every PR** (`checks.yml`, separate workflow): unit
   tests, published-prompt immutability (1.3), golden validation and
   few-shot overlap (2.6 / 1.4). Running them on every PR includes the
   "whenever `prompts/` or `golden/` change" of 2.6.
4. **PR comment:** `gh pr comment <n> --edit-last --create-if-none
   --body-file comment.md` — one comment edited in place; needs
   `pull-requests: write`; only `eval.yml` comments, so it never overwrites
   another workflow's comment. The header shows the commit (4.1).
5. **Several pushes:** `concurrency` grouped per PR with
   `cancel-in-progress: true`; a new push cancels the run in progress, which
   sends no Telegram.
6. **Fork PRs:** secrets are not available, so the run aborts as a
   configuration error (1.6b) with "secrets unavailable (fork PR)" and the
   check fails (an unmeasured prompt does not merge). `pull_request_target`
   is never used.
7. **Required check:** the `eval` job is a required status check on `main`
   (step in [`initial-setup.md`](../guides/initial-setup.md)).

The golden set stays frozen as edition 1; every test and every Phase 6
scenario changes prompts, never the golden set.

**Definitions.**
- *Path filter (`paths`)*: Actions rule that starts a workflow only when the
  PR changes files under given paths.
- *Required status check*: branch protection that disables merging until the
  check passes; it is what makes the evaluation a gate.
- *Sticky comment*: one PR comment edited on each run instead of a new one
  per push.
- *Fork*: a copy of the repository under another account.
- *Concurrency group*: Actions runs that share a key; with
  `cancel-in-progress`, a new run cancels the older one in the group.

**Why.**
- A workflow skipped by path filtering leaves its required check "Pending"
  and blocks the merge; path filters on required workflows are discouraged
  [1].
- `gh pr comment --edit-last` edits the last comment of the current user;
  `--create-if-none` creates it if none exists; `--body-file` reads the body
  from a file [2].
- A concurrency group keyed by the PR's head ref with `cancel-in-progress`
  cancels the earlier run of the same PR [3].
- Secrets are not passed to the runner for workflows triggered from a fork;
  `GITHUB_TOKEN` is the only exception [4].
- The paired comparison runs both sides with the PR's code (3.6), so only
  prompt and gate-config changes produce a measurable difference (our
  reasoning).

**Considered, not adopted.** A workflow-level `paths` filter (pending
required check); third-party actions for path filtering or sticky comments
(`git diff` and `gh` are enough); running the eval on `src/` (blind
comparison, ~US$ 1.50 per push); `pull_request_target` (exposes secrets to
fork code).

**How it is tested.** Unit tests for `is_eval_relevant`
(`prompts/classifier/v2.yaml` → yes, `src/...` → no, `golden/...` → no,
`config/gate.yaml` → yes, empty list → no) and for the "gate config changed"
header flag; end to end by the Phase 6 scenarios, which all change
`prompts/` or `config/gate.yaml`.

## 5.2 Run history storage

**Decision (2026-11-04): no run history is stored for CI.** Both reasons for
it are gone: the baseline is re-run in each PR job (3.6) and the trend chart
was dropped (4.1).

What exists without storing anything:

| Where | Runs | What it keeps | How long |
|---|---|---|---|
| PR comment | CI | Verdict, headline table, top cases, commit | Permanent (public repo) |
| CI artifact | CI | Full HTML report | 90 days (GitHub default) |
| Telegram chat | CI | Summary + attached report | As long as the chat exists |
| `docs/sample-report/`, `docs/noise-check/` | — | One sample report; the "nothing changed" check | Committed |
| Langfuse (local) | Local | Experiments, traces per case, scores, side-by-side comparison | While the Docker volume exists |
| `runs/` SQLite (gitignored) | Local | Per-case results queried by code (e.g. observed difficulty, 2.3) | Local only |

In CI, `SQLiteRunRepository` writes to a temporary file discarded with the
runner (same code, no special adapter). This replaces the "run history kept
in the repository" note of the earlier "Python only" decision; the
planning §6 diagram now shows `runs/` on the local machine.

**Definitions.**
- *Run history*: stored results of past evaluation runs, kept to compare
  over time.
- *Artifact*: a file a GitHub Actions job publishes for download on the run
  page.
- *Retention*: how long GitHub keeps an artifact; 90 days by default,
  changeable with `retention-days`.

**Why.**
- Artifacts and logs are kept for 90 days by default; retention can be
  changed per repository or per artifact with `retention-days` [5].
- With the baseline re-run in the same job, nothing from a previous run is
  read by the gate (3.6); without a trend chart, nothing reads CI history at
  all (4.1).

**Considered, not adopted.** Committing CI results to the repository (bot
commits on PRs, noise and conflicts); publishing a history site (nothing is
published); Langfuse Cloud for CI runs (reopens the local-only Langfuse
decision; an extra account for data nobody reads).

**How it is tested.** Nothing new: the decision removes a feature. Existing
coverage: `RunRepository` tests with fakes (Phase 3); `runs/` and `*.sqlite`
stay in `.gitignore`.

## 5.3 Dockerfile and CI environment

**Decision (2026-11-04).**

1. **CI runs directly with uv, no container:** `astral-sh/setup-uv` with a
   full version pinned and `enable-cache: true`, then `uv sync --locked` and
   `uv run eval`. Reproducibility comes from `uv.lock` + `.python-version`,
   the same files locally and in CI.
2. **The Dockerfile is for running locally without installing anything** and
   is a portfolio deliverable (planning §11): `docker build`, then
   `docker run --env-file .env`. Recipe:
   - base `python:3.12-slim`;
   - uv binary copied from `ghcr.io/astral-sh/uv:<version>` (exact version
     pinned at implementation);
   - dependency layer: copy `pyproject.toml` + `uv.lock`, run
     `uv sync --locked --no-install-project`;
   - project layer: copy the rest, run `uv sync --locked`;
   - BuildKit cache mount for uv's cache;
   - default command `uv run eval`.
   The image packages the runner, the golden set, prompts, config and report
   templates.
3. **Secrets never in the image:** only at run time (`--env-file .env`),
   never through `ARG` or `ENV`. A new `.dockerignore` excludes `.env`,
   `.venv`, `runs/`, `.cache/`, `*.sqlite` and `.git`. The adapter selector
   `NOTIFIER` is an env var; thresholds come from `config/gate.yaml` (mount
   `-v ./config:/app/config` to try other values).
4. **Keeping the Dockerfile working:** `.github/workflows/docker.yml` runs
   `docker build` (no push) when `Dockerfile`, `.dockerignore`,
   `pyproject.toml`, `uv.lock` or `.python-version` change. It is not a
   required check, so a workflow path filter is safe here (the 5.1 pitfall
   applies only to required checks).
5. Local Langfuse keeps its own Docker Compose in `infra/langfuse/`,
   unchanged.

**Relation to the BASWE guide.** The guide asks for a Dockerfile that
packages the eval runner, the golden dataset and the reporting layer and
accepts env vars for the API key, the alert webhook and threshold configs;
it does not require CI to run inside the container. This decision follows
it except for thresholds, which live in `config/gate.yaml` so a threshold
change goes through the PR and the gate (portfolio rule: env vars hold
secrets only).

**Definitions.**
- *Docker image / Dockerfile*: a package with the OS, Python and
  dependencies ready to run / the recipe that builds it.
- *`uv.lock`*: fixes the exact version of every dependency; `uv sync
  --locked` installs exactly that and fails if the lock is out of date with
  `pyproject.toml`.
- *`setup-uv`*: Astral's GitHub Action that installs uv; `enable-cache`
  keeps downloaded packages between runs.
- *`.dockerignore`*: what never goes into the image.
- *Layers and build cache*: Docker reuses unchanged build steps, so
  installing dependencies before copying the code avoids reinstalling them
  when only code changes.

**Why.**
- In GitHub Actions, `setup-uv` with a full version tag (no moving tags) and
  `enable-cache: true`, then `uv sync --locked`, which installs from the
  lock without modifying it and fails if it is out of date [6].
- In Docker: a slim Python base, the uv binary copied from a pinned image,
  dependencies installed with `--no-install-project` before the code is
  copied, a BuildKit cache mount, and a `.dockerignore` [7]. `--locked` is
  used instead of the tutorial's `--frozen` to match CI.
- Building an image on every PR would slow the gate without improving
  reproducibility, which the lock already guarantees (our reasoning).

**Considered, not adopted.** Running the CI job inside the image
(`container:` or `docker run`): rebuilds per PR, no gain over the lock.
Publishing the image to GHCR: nothing is published. Dropping the
Dockerfile: it is a listed deliverable and lets people run without uv.

**How it is tested.** A unit test reads `.dockerignore` and checks that
`.env` is listed; `docker.yml` confirms the image builds; locally,
`docker run --env-file .env` runs the eval.

## References

1. GitHub Docs — Troubleshooting required status checks (Handling skipped but required checks). https://docs.github.com/en/enterprise-server@3.5/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/troubleshooting-required-status-checks
2. GitHub CLI manual — gh pr comment. https://cli.github.com/manual/gh_pr_comment
3. GitHub Docs — Using concurrency. https://docs.github.com/actions/using-jobs/using-concurrency
4. GitHub Docs — Using secrets in GitHub Actions. https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
5. GitHub Blog — Ability to change retention days for artifacts and logs (2020-10-08). https://github.blog/changelog/2020-10-08-github-actions-ability-to-change-retention-days-for-artifacts-and-logs/
6. pydevtools — Setting up GitHub Actions with uv. https://pydevtools.com/handbook/tutorial/setting-up-github-actions-with-uv/
7. pydevtools — How to use uv in a Dockerfile. https://pydevtools.com/handbook/how-to/how-to-use-uv-in-a-dockerfile/
8. BASWE — 15 AI Engineering Projects That Actually Land Jobs, Project 1, Phase 5 (guide PDF, local copy).
