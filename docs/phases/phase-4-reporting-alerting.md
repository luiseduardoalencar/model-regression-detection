# Phase 4 — Reporting and alerting

**Goal:** turn a run into something a human acts on — an HTML report with
the regressed cases side by side and a Telegram alert with the report
attached. (Slow-drift detection was removed with the scheduled runs on
2026-11-04; cumulative drops are caught by the absolute floor, decision 3.4.)

**Status:** decisions closed (4.1 and 4.2, 2026-11-04). Not implemented yet.
Implementation checklist: [`planning.md` §7, Phase 4](../planning.md#phase-4--alerting-and-reporting).

## Already fixed before this phase

- Static HTML report (Jinja2), uploaded as a CI artifact and sent as a file
  in the Telegram alert; no web layer ([`foundations.md`](../foundations.md) F6).
- `Notifier` port with `TelegramNotifier` and `ConsoleNotifier` for local
  runs (the Telegram call itself is decided in 4.2).
- Inconclusive runs carry a distinct message (decision 1.6).
- The report shows the metrics of 3.1, the judge results of 3.2, cost per
  run, cache-friendly re-runs and the prompt diff between baseline and
  candidate (1.3).

## 4.1 Report content

**Decision (2026-11-04).** One self-contained HTML report per run, the same
file locally and in CI. Sections, most important first:

1. **Verdict header:** run verdict (`passed` / `warning` / `blocked` /
   `inconclusive`) and the rule(s) that fired; "classifier prompt vN
   (candidate) vs vM (baseline)" with each version's `change_note` (1.2);
   golden edition; judge prompt version; served model IDs on both sides;
   judge calibration status ("uncalibrated" when 3.3 targets are not met);
   commit SHA and date; "gate config changed in this PR" when
   `config/gate.yaml` changed (5.1). An `inconclusive` run shows "no verdict".
2. **Headline table:** one row each for category, format and summary
   (summary marked advisory); columns baseline, candidate, delta (pp),
   regressions, improvements, net drop, next to the 5 / 7 thresholds (3.5).
   Below it, one context line: adversarial flips, infra errors (x / 140),
   **distance to the absolute floor** in cases ("floor not set yet" until the
   first measured run of classifier prompt v1, 3.4), and the count of cases
   whose output changed without a verdict change (3.6).
3. **Cases by severity**, in the 3.6 order: violated invariants → category
   regressions → format regressions → summary regressions → improvements →
   exact→acceptable changes → infra errors excluded from the comparison.
   Each case is a collapsible `<details>` block: `id`, expected category,
   label before → after, summary before → after, judge evidence per item, and
   the email text (collapsed).
4. **Per-category and slice deltas**, always with n; rows with a net drop ≥ 2
   cases highlighted (verdict unchanged, 3.6).
5. **Classification detail (3.1):** strict and acceptable accuracy, macro-F1,
   per-category precision / recall / F1 (baseline, candidate, delta);
   candidate's 7×7 confusion matrix plus the "no answer" column, baseline's
   matrix collapsed.
6. **Prompt diff** between baseline and candidate YAML files (1.3).
7. **Cost and run configuration:** cost, tokens, latency and cache hits per
   side; threshold values used and the config file they came from.

Rendering rules:
- Jinja2 with `autoescape=select_autoescape(["html", "xml"])`: adversarial
  emails may contain markup and must render as text.
- One file, inline CSS, no JavaScript, no external links, fonts or images, so
  it opens offline from the Telegram attachment.
- Report labels in English; emails and summaries in Portuguese as stored in
  the golden set.
- `docs/sample-report/` (planning §11) is generated from a real run.

**PR comment = short rendering of the same data:** sections 1 and 2, the
first 5 cases of section 3 (`id`, label and summary before → after), and a
pointer to the full report (CI artifact and Telegram). How the comment is
posted is decided in Phase 5.

**Not in the report:**
- **Trend chart of the last N runs: not adopted.** It needs run history stored
  across PRs, which 3.6 made unnecessary for the gate; the question it
  answers ("are we slowly getting worse?") is covered by the absolute floor,
  and the distance-to-floor line shows it without history. This leaves 5.2
  without its only reason; confirmed in Phase 5.
- **Observed vs expected difficulty per case:** the PR report shows only the
  `expected_difficulty` slice (3.1). The per-case comparison with observed
  difficulty over run history (2.3) is a local analysis on the SQLite runs,
  outside the PR report.
- Considered, not adopted: an interactive JS report with filters and sorting
  (heavy for 140 cases); latency and cost distribution charts (the numbers in
  section 7 are enough).

**Definitions.**
- *Self-contained HTML*: a single file with everything embedded; nothing is
  fetched when it opens.
- *`<details>`*: a native HTML element that shows a collapsible block without
  JavaScript.
- *Autoescape / XSS*: cross-site scripting is text in a page being run as
  code; autoescaping converts characters such as `<` to `&lt;` so input is
  shown as text.
- *Distance to the floor*: how many more failing cases would put the metric
  below the absolute floor of 3.4.

**Why.**
- Comparison tools lead with aggregate cards showing the delta against the
  base and regression / improvement counts, then rows sorted so the most
  affected cases come first, with a per-case diff of base and comparison
  outputs [1].
- Baseline comparison views pair the two runs' outputs per dataset item and
  put summary stats in the header [2].
- Promptfoo's HTML output is a standalone file with pass/fail statistics and
  side-by-side outputs; it embeds the eval config, so what goes in the file
  must be chosen deliberately [3].
- A PR comment should be readable in seconds: headline deltas first, a table
  against thresholds, then three to five concrete examples that newly pass or
  fail; one comment edited in place [4].
- Never disable Jinja2 autoescaping; use `select_autoescape` [5].

**How it is tested.** Unit tests render the report from hand-made case
results and check: section order; an email containing `<script>` appears
escaped; "floor not set yet" when no floor is configured; "no verdict" on an
`inconclusive` run; the PR comment lists at most 5 cases.

## 4.2 Telegram message

**Decision (2026-11-04).**

- **One message per run:** a single Bot API `sendDocument` call with the
  HTML report as the file and the summary as its caption, so the summary and
  the report arrive together in one bubble. Replaces the earlier plan of
  `sendMessage` (summary) + `sendDocument` (report).
- **Caption content** (`parse_mode=HTML`, at most 1024 characters), in the
  same order as the report:
  1. Verdict emoji and name: ✅ PASSED, 🟡 WARNING, 🔴 BLOCKED,
     ⚪ INCONCLUSIVE.
  2. Candidate vs baseline prompt versions and golden edition.
  3. The rule(s) that fired ("No rule fired" on `passed`).
  4. Headline table in a `<pre>` block: category, format, summary (marked
     advisory) × baseline, candidate, delta (pp), net drop.
  5. Context line: adversarial flips, infra errors (x / 140), distance to
     the absolute floor.
  6. Top 3 cases from report section 3 (`id`: label before → after), then
     "+N more in the report".
  7. Cost and the PR link (public repository). No CI artifact link (it
     needs a GitHub login; the report is attached).
- **Inconclusive:** "no verdict", infra errors (x / 140, > 2 %) and
  "re-run the job"; no headline table; the report is still attached.
- **When to send:** every PR gate run (each push to an open PR is a new
  run). `passed` is sent with `disable_notification=true` (arrives silently,
  as a receipt that the gate ran); `warning`, `blocked` and `inconclusive`
  arrive with sound.
- **Never changes the verdict:** a Telegram failure is logged; the exit code
  stays the one of 3.4 (0 / 0 / 1 / 2). The gate is the GitHub check.
- **One summary builder:** the same function builds the text;
  `TelegramNotifier` sends it as the caption, `ConsoleNotifier` prints it
  without tags plus the report path (local runs).
- Message text in English (repository rule); `<`, `>` and `&` are escaped.
- If the Telegram secrets are missing, the console notifier is used
  (CI wiring decided in Phase 5).
- The report is far below the 50 MB bot upload limit.

**Definitions.**
- *Caption*: the text attached to a file in Telegram, shown in the same
  bubble.
- *`disable_notification`*: Bot API flag that delivers a message without
  sound.
- *`parse_mode=HTML`*: lets the message use a small set of HTML tags (bold,
  `<pre>` for monospaced, aligned tables).

**Why.**
- `sendDocument` accepts a caption of 0–1024 characters after entity
  parsing, a `disable_notification` flag ("sends the message silently") and
  files up to 50 MB [6].
- Alerting practice: good signal, very low noise; frequent alerts get
  skimmed or ignored [7]. Only results that need action make a sound;
  `passed` is a silent receipt.
- A PR-gate summary leads with the verdict and headline deltas, then a few
  concrete cases [4] (3 here because of the caption limit; 5 in the PR
  comment, 4.1).

**Considered, not adopted.** Two messages (`sendMessage` + `sendDocument`):
the only gain is the 4096-character limit, not needed, and the summary would
be separated from the report. Sending only on non-passed runs: loses the
confirmation that the gate ran. Bot buttons or commands: they need a server
listening to Telegram, which conflicts with "nothing is deployed".

**How it is tested.** Unit tests with hand-made results: the caption stays at
most 1024 characters in the worst case (many regressions, long IDs) by cutting
the list to "+N more"; `disable_notification` is true only for `passed`;
special characters are escaped; `inconclusive` has no table; a simulated
Telegram failure keeps the exit code; the console notifier prints the same
content.

## References

1. Braintrust — Compare experiments. https://docs.braintrust.dev/evaluate/compare-experiments
2. Langfuse — Compare view with baseline support (changelog, 2025-11-06). https://langfuse.com/changelog/2025-11-06-compare-view-baseline-support
3. Promptfoo — Output formats. https://www.promptfoo.dev/docs/configuration/outputs
4. Tian Pan — Eval as a pull request comment, not a job (2026-05-01). https://tianpan.co/blog/2026/05/01/eval-as-pull-request-comment-not-a-job
5. CodeQL — Jinja2 templating with autoescape=False. https://codeql.github.com/codeql-query-help/python/py-jinja2-autoescape-false/
6. aiogram — sendDocument (mirror of the Telegram Bot API documentation). https://docs.aiogram.dev/en/latest/api/methods/send_document.html
7. O'Reilly — Monitoring Distributed Systems (chapter of Google's *Site Reliability Engineering*). https://www.oreilly.com/radar/monitoring-distributed-systems
