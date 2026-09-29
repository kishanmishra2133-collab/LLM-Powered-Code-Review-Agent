# Phases: ReviewLens build plan

Phases are ordered by dependency, not by calendar. Each ends with something demoable and pushed to GitHub, so stopping after any phase still leaves a real project.

| Phase | Focus | You can show |
|---|---|---|
| 1 | Engine and GitHub Action (baseline graph) | A real review comment on a real PR |
| 2 | Eval set and baseline numbers | A results table |
| 3 | Verification node and measured improvement | Before and after metrics |
| 4 | Demo page and ship | A live link, README, demo GIF |
| Later | Optional extras | Each a separate resume bullet |

Phase 2 must come before Phase 3: without a baseline you cannot claim an improvement.

---

## Phase 1: Engine and GitHub Action

**Goal:** given a PR, post useful, correctly anchored comments, through a LangGraph workflow with no verify step yet.

### Setup
- [ ] Repo with the layout from `architecture.md` (section 3); Python 3.11+, Ruff, mypy, pytest; CI
- [ ] A throwaway test repo with a few PRs you control: one with a planted bug, one clean, one with a lockfile change
- [ ] Try CodeRabbit's free tier or PR-Agent on it, and write a few lines in `notes/competitors.md` on what they got wrong. These notes feed the README's "why build this"
- [ ] Get a Gemini API key; check current model IDs and pricing and record them in `notes/models.md`

### Build
1. **Models and config**
   - [ ] Pydantic models: `PRRef`, `DiffFile`, `DiffLine`, `Finding`, `Usage`, `ReviewState`
   - [ ] `pydantic-settings` config
2. **Clients**
   - [ ] GitHub client: PR meta, diff, pagination, retry with backoff
   - [ ] Gemini client: structured output, retry, token and cost accounting
3. **Stage functions (plain, each with tests)**
   - [ ] `fetch`, `filter`, `annotate`, `review`, `validate`, `finalize`
   - [ ] Diff parser with stable line IDs; tests for added, removed, and context lines, multiple hunks, renames, and the no-newline marker
   - [ ] `validate` drops invalid IDs, dedupes, applies the confidence threshold, and caps at 8
   - [ ] Review prompt `review_v1.md`
4. **LangGraph wiring**
   - [ ] Linear graph: fetch, filter, annotate, review, validate, finalize
   - [ ] Retry policy on `review` for transient errors and one retry on schema failure
5. **Adapters**
   - [ ] CLI: `reviewlens review <pr-url>` (dry run)
   - [ ] GitHub Action: one review with inline comments and a summary, with the head-SHA idempotency marker
6. **Security basics**
   - [ ] Data-not-instructions prompt framing; secret redaction; a test PR with injected instructions

### Exit criteria
- The Action posts comments on your test repo, and they land on the correct lines
- Re-running on the same commit does not duplicate the review
- A lockfile-only PR produces no review and a clear note
- Line parsing and validation are well covered by tests

**Cut line:** drop risk-based file prioritization (just skip and say so) and dedupe. Never drop line validation.

---

## Phase 2: Eval set and baseline

**Goal:** turn "it seems okay" into numbers. This phase is what makes the project stand out, and the labeling is your judgment, not the agent's.

- [ ] Pick 3-4 active, mid-size Python open-source repos
- [ ] Collect and label about 30 PRs: roughly 20 with real issues (labels from reviewer change requests and follow-up fixes) and 8-10 clean
- [ ] Cache each diff in `eval/dataset/diffs/`, write `cases.jsonl`, and keep `labeling-notes.md` explaining each label
- [ ] `eval/score.py`: matching (same file, overlapping lines with tolerance), precision, recall, F1, clean-PR false-positive rate, comments per PR, cost, p50 and p95 latency
- [ ] `reviewlens eval run --tag baseline` using cached diffs; saves a run file with git SHA, prompt version, and model
- [ ] `reviewlens eval compare a.json b.json`
- [ ] Run the baseline and record the numbers; try one or two cheap variations (a stricter prompt or a different model) as extra runs
- [ ] Read every false positive and every miss; write the patterns in `notes/failure-analysis.md`. These drive Phase 3

### Exit criteria
- One command produces the metrics table
- At least three saved runs
- A short list of concrete failure patterns

**Cut line:** if labeling drags, stop at 20 PRs (12 with issues, 8 clean) and state the sample size honestly. Do not skip clean PRs.

---

## Phase 3: Verification node and measured improvement

**Goal:** raise precision with a verification step and prove it on the eval set.

- [ ] Write `verify_v1.md`: given a finding and surrounding code, try to refute it; return supported, refuted, or unclear with a reason
- [ ] Add the `verify` node with concurrent per-finding calls
- [ ] Add the conditional edge after `validate`: go to `verify` only if there are findings and verification is enabled
- [ ] Add a retry policy to `verify`
- [ ] Config flag so the same graph compiles with or without `verify`
- [ ] Record refuted findings in `dropped` with the reason
- [ ] Run `--tag verify` and compare with the baseline: precision, recall, cost, latency. Check where recall fell
- [ ] Write up what worked, what did not, and one surprising finding

### Exit criteria
- A before and after table on the same eval set
- A clear answer to "did it help, and what did it cost?"

**If verification does not improve precision:** that is still a valid result. Report it, then try a stricter threshold or a different verify prompt. An honest negative result with analysis beats a forced positive one.

---

## Phase 4: Demo page and ship

**Goal:** a stranger pastes a PR URL and sees a review in under 30 seconds. See `design.md`.

### Backend
- [ ] FastAPI: `GET /api/review` (SSE), `GET /api/examples`, `GET /api/health`
- [ ] Map LangGraph per-node updates to SSE events; send a structured `diff` event
- [ ] JSON file cache keyed by repo, PR, head SHA, and prompt version
- [ ] Daily budget counter, size cap, strict PR URL parsing, public repos only
- [ ] Pre-run and cache 3 example PRs: a good catch, a clean PR, and a large PR with skipped files

### Frontend
- [ ] `tokens.css`, `base.css`, `app.css`; landing and results layouts
- [ ] Input with validation; numbered progress list
- [ ] Diff table; margin notes with alignment and the arrival animation
- [ ] Error and empty states with the copy from `design.md`
- [ ] Light and dark via `prefers-color-scheme`

### Ship
- [ ] Deploy to Fly.io, Render, or Railway; secrets set; HTTPS confirmed
- [ ] README: pitch, demo GIF, results table (baseline versus verify), architecture diagram, how to run locally, how to add the Action to a repo
- [ ] "What did not work" (2-4 honest items) and "Limitations" (from `architecture.md`, section 11)
- [ ] Short demo video: paste PR, watch stages, click a note, show the eval table
- [ ] Clean the repo: remove dead code, pin dependencies, add a license and `.env.example`
- [ ] Update the four docs to match what was actually built

### Exit criteria
- The live URL works on desktop and phone
- The budget cap and size cap were tested (try to break them)
- A PR with HTML or script text in its diff renders safely
- With the Gemini key removed, the examples still work

**Cut line:** drop dark mode first. Keep the margin notes; they are the memorable part.

---

## Later (not v1)

| Item | What it adds | Measure it with |
|---|---|---|
| Langfuse or LangSmith tracing | Observability, cost per node | Trace screenshots |
| GitHub App with webhooks | Multi-repo install, signature verification | Live install on a second repo |
| Incremental review on new commits | No repeated comments | Duplicate rate |
| Per-repo rules file | Customization | Rule-specific precision |
| Model comparison (two Gemini models) | Cost and quality trade-off | Table of cost versus F1 |
| Concurrency and per-IP limits | Needed only if the demo gets real traffic | Load test |

Repo retrieval with embeddings is intentionally not on this list, since your RAG project already covers it.

---

## Building with Antigravity

An AI coding agent writes most of the code quickly, so the risks shift: code you have not understood, tests that pass without proving anything, and quiet scope creep.

1. **Give the agent the docs.** Keep the four docs in the repo root so every task starts from the same source of truth.
2. **One checkbox at a time.** Ask for a small, reviewable change (for example "diff parser plus its tests"), not a whole phase.
3. **Tests first for risky parts.** Line mapping, validation, and scoring are where silent bugs hide. Have the agent write tests from the cases in `architecture.md` (section 4.5), and read them yourself.
4. **Review every diff.** You must be able to explain any part of this in an interview. If you cannot, ask for a walkthrough or simplify it.
5. **Keep judgment work yours:** choosing and labeling eval PRs, reading every false positive and miss, deciding what the numbers mean, and writing "what did not work".
6. **Verify facts the agent may get wrong:** Gemini model IDs and pricing, SDK method names, LangGraph streaming and retry APIs, and GitHub API parameters all change.
7. **Commit at each exit criterion**, so a bad agent change is easy to roll back.

## Rules to stay on track

1. Ship at each phase boundary: push, tag, update the README.
2. Precision first. A change that adds comments without improving the eval does not go in.
3. No new feature without a way to measure it.
4. If one problem keeps resisting several agent attempts, make a cut-line decision instead of looping.
5. Write failure notes as you go.

## Interview questions this prepares you for

- How did you evaluate the agent, and how do you know the numbers mean anything with 30 PRs?
- How do you stop the model from citing wrong line numbers?
- Why LangGraph here, and when would you not use it?
- What did verification cost in latency and money, and was it worth it?
- How do you defend against prompt injection in a tool that reads untrusted code?
- How would you scale this to a hundred repos?
- What would you change if precision were fine but recall were the problem?

## Definition of done (v1)

- [ ] Action posts correctly anchored comments on a real repo
- [ ] Eval set of about 30 PRs (or a documented smaller number) with saved runs
- [ ] Before and after table in the README, with honest caveats
- [ ] Live demo page with a budget cap
- [ ] Demo GIF or video
- [ ] The four docs updated to match what was built
