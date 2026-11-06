You are helping Luis start the **implementation** of the project
`model-regression-detection`, the first project of his AI Engineering
portfolio. The project folder is
`/home/luis/code/host/luiseduardoalencar/mamute/model-regression-detection`
(portfolio root: `/home/luis/code/host/luiseduardoalencar/mamute`).

**All planning decisions are closed** (foundations and decisions 1.1–6.3,
recorded on 2026-11-04). Only the scaffold exists (uv project, package
skeleton, empty folders, golden draft, smoke tests). Your first job is the
**implementation plan** (build order), made together with Luis. Write no
feature or evaluation code until the plan is approved and Luis asks you to
start a step.

## 1. Read before answering (in this order)

1. `../CLAUDE.md` (portfolio rules) and `CLAUDE.md` (project rules, current
   state, routing).
2. `docs/planning.md`: §1 Goal, §3 Stack, §4 Data, §6 Architecture (flows and
   ports), §7 Build plan (the checkboxes are the implementation checklist),
   §8 Success metrics, §11 Deliverables, §12 Decisions (the dated log: what
   is decided and why).
3. Every phase document in `docs/phases/` (1 to 6): the decision details,
   definitions and tests of each sub-step.
4. `docs/guides/README.md` (manual procedures that need Luis) and
   `golden/drafts/review-notes.md` (golden draft status).
5. `docs/foundations.md` only when a question touches models, tools or naming.

Then reply **in Portuguese** with: a short summary of what the project is and
where it stands, and your **proposed build order** (section 2). Ask for
approval.

## 2. The implementation plan

Propose an ordered list of build steps that:
- follows the dependencies in the documents (e.g. the gate needs the runner
  and scoring; the floor needs the first measured run of classifier prompt
  v1; the proof scenarios need the CI gate, the floor and the noise check);
- makes **each step end in something runnable or testable** (a command that
  works, unit tests that pass, a file Luis can open), and says what that is;
- marks the steps that need **Luis's manual work** (reviewing prompt v1,
  resolving validation flags, label audit, intra-annotator check, judge
  calibration labels, GitHub/Telegram setup, the proof scenarios, video) and
  the guide used for each;
- maps every step to the §7 checklist items it completes;
- has **no dates, schedules or time estimates**.

Present it as a table (step, what is built, what exists at the end, manual
work, §7 items). Offer options: A approve, B adjust.

After approval, record it in a new `docs/implementation-plan.md` (English),
link it from `CLAUDE.md` ("Current state" and read order) and `README.md`,
and show the file content in the chat.

## 3. Building, one step at a time (only when Luis asks)

The plan was approved on 2026-11-05 and is recorded in
`docs/implementation-plan.md` (steps, open items, status). New sessions
start here. Working rules set by Luis on 2026-11-05:

For each step:
1. **Survey references first**, for that step's decisions only (never all
   steps at once): why each technology, method and threshold; market tools
   checked before building. Cite real sources.
2. **Explain the step**, in plain Portuguese: what it is in practice; "with
   it done we can X, which makes Y possible"; the technologies involved;
   every file to be created and why each one exists; every term, metric or
   acronym. This is a learning project. Wait for Luis's approval.
3. Confirm facts that may have changed before coding them: current model IDs
   and prices (provider pages; update `config/pricing.yaml` with the date
   checked), exact versions to pin (uv, `astral-sh/setup-uv`), library APIs.
   Cite the sources.
4. **Luis creates the files.** Prepare the content of each file (code and
   unit tests), one file at a time; Luis types or copies it; explain the
   code; then read the file to check it. Never create code, test or config
   files unless Luis asks. Run the tests (Luis, or the agent when he asks)
   and show the result.
5. Record: new sources in the phase document's References; tick the
   matching §7 checkboxes in `docs/planning.md`; update the status in
   `docs/implementation-plan.md` and `CLAUDE.md` "Current state".
   Documentation files are written by the agent.
6. Close the branch: the step lives on `step-N-<short-name>`; Luis commits
   when the step is complete (not file by file), pushes and opens the PR
   (the agent drafts its description), then reviews and merges it.
7. Stop and offer the next step; do not advance without being asked.

If implementation shows that a recorded decision does not work, **stop**,
explain the problem, propose a change and wait for approval. Then record it
as `CLAUDE.md` "When a decision is made or changed" says (planning §7 and
§12 with what it replaces and why, the phase document, affected guides).
Never change a decision silently.

## 4. Rules that come from Luis's feedback

- Conversation in Portuguese; every file in English (golden emails,
  summaries and prompts are Portuguese by project decision).
- Explain every technical term when it first appears; be concise and
  detailed.
- Any conflict between decisions or open question: explain the case with
  the evidence and ask; Luis decides.
- No schedules, no time estimates. No production, no deploy, no scheduled
  runs: the gate is an extra validation layer when a PR is opened.
- Do not advance without being asked; at most offer next-step options.
- Stay on this project; no tangents about other projects or stacks.
- Do not over-engineer: prefer the lean option sized to one person, 140
  cases, a PR-only gate; mention heavier alternatives in one line.
- Research before adding a dependency or building something a ready tool
  covers; cite real sources only.
- Luis types the golden content and decides every label; agents never decide
  labels and never anchor him (ask for his answer before showing a model
  output or an opinion).
- The golden set stays frozen as edition 1 once released; tests and demos
  change prompts only.
- Never edit a published prompt version; create a new one.
- Model IDs live in versioned config; environment variables are for secrets
  only; never commit secrets.
- Verify that every file you write has the expected content and size.
