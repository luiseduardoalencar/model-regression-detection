# Guide — Initial setup

**Used in:** once, before the first local run (Phase 1) and before the first
CI run (Phase 5). Exact commands are confirmed when the corresponding code
and files exist; steps marked *(at implementation)* depend on them.

## 1. OpenAI

1. Create (or reuse) an OpenAI API key for this project.
2. Set a monthly usage limit on the project (cost control, planning §9).
3. Put the key in the local `.env` as `OPENAI_API_KEY` (the file is
   gitignored; `.env.example` lists the variable names only).

## 2. Local Langfuse

1. Start Langfuse with Docker Compose from `infra/langfuse/`
   *(at implementation)*; the UI opens at `http://localhost:3000`.
2. Create a user and a project (`model-regression-detection`).
3. Create API keys in the project settings and put them in the local `.env`:
   `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.
4. These keys are local only; they are never added to GitHub.

## 3. Telegram bot

1. In Telegram, talk to `@BotFather`, run `/newbot`, choose a name; copy the
   bot token.
2. Send any message to the new bot (or add it to a group).
3. Get the chat ID from the Bot API `getUpdates` response *(the agent can
   help read it; never paste the token in public places)*.
4. Put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the local `.env`.

## 4. GitHub

1. Create the public repository and push the first commit (build step 1):
   `gh repo create model-regression-detection --public --source=. --remote=origin --push`.
   No workflow exists yet, so pushes trigger nothing until step 14.
2. In Settings → Secrets and variables → Actions, add:
   `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. Never print secrets in workflow logs.
4. In Settings → Branches (or Rules → Rulesets), protect `main`: require a
   pull request and require the `eval` status check to pass before merging
   *(at implementation: the check appears after the first run of
   `eval.yml`)*. This is what turns the evaluation into a gate (decision
   5.1).
5. `eval.yml` declares `permissions: pull-requests: write` so it can post
   the PR comment.

## 5. Run with Docker (optional)

For running the eval without installing Python or uv (decision 5.3).
Commands are confirmed when the Dockerfile exists *(at implementation)*.

1. `docker build -t model-regression-detection .`
2. `docker run --rm --env-file .env model-regression-detection` — secrets
   come only from `.env` at run time; the image never contains them
   (`.dockerignore` excludes `.env`).
3. To try other thresholds, mount the config folder:
   `-v ./config:/app/config`.

## Checklist

- [ ] `.env` has `OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
      `LANGFUSE_HOST`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- [ ] `.env` is gitignored; `.env.example` is committed.
- [ ] GitHub has the three CI secrets.
- [ ] `main` requires the `eval` status check.
- [ ] OpenAI monthly limit is set.

## References

1. Langfuse — Self-host locally (Docker Compose) — https://python-sdk-v2.docs-snapshot.langfuse.com/self-hosting/local
2. OpenAI — API pricing — https://developers.openai.com/docs/pricing
3. Telegram — Bot API (`getUpdates`, `sendMessage`, `sendDocument`) — https://core.telegram.org/bots/api
4. GitHub — Using secrets in GitHub Actions — https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
5. GitHub — Troubleshooting required status checks — https://docs.github.com/en/enterprise-server@3.5/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/troubleshooting-required-status-checks
