# PRD: ReviewLens (working name, rename before publishing)

An LLM code review agent, built as a LangGraph workflow, with a measured track record, a GitHub Action, and a public "paste a PR" demo page.

| | |
|---|---|
| **Purpose** | Portfolio project for AI engineer roles |
| **Stack** | Python, FastAPI, Gemini API, LangGraph, GitHub API, plain HTML/CSS/JS |
| **Build approach** | Built with an AI coding agent (Antigravity); scope is controlled by phase exit criteria |
| **Status** | Draft v2 (simplified) |

---

## 1. Summary

ReviewLens reads a pull request, finds real problems in the changed code, and reports them as comments anchored to exact lines. It does not try to out-feature CodeRabbit or Copilot review. What sets it apart is that **every quality claim is backed by numbers** from a labeled evaluation set: precision, recall, cost, and latency, compared before and after each improvement.

One review engine, three ways to use it:

1. **GitHub Action** that posts a review on a PR.
2. **Demo page** where anyone pastes a public PR URL and watches the review stream in.
3. **Eval harness** (CLI) that scores the engine on labeled PRs and produces the results table.

## 2. What this project should show

Your resume already has a RAG chatbot. This project covers the skills that one does not:

- An **agent workflow** (LangGraph: multi-step, conditional, with retries and a verification step)
- **Structured output** validated against a schema
- **Evaluation** with real metrics and a before/after comparison
- **Real-world integration** (GitHub API and Actions)
- **Reliability and safety** (line validation, cost tracking, prompt-injection defenses)

Repo retrieval with embeddings is deliberately out of scope so it does not overlap with the RAG project.

## 3. Goals and non-goals

### Goals

- G1. **High-precision** findings: few comments, mostly correct.
- G2. **Measured quality** on 30 labeled PRs, with a before/after table.
- G3. A stranger can **try it in under 30 seconds** with no install.
- G4. Show production habits: idempotency, cost and latency tracking, failure handling, injection defenses.
- G5. Every phase ends demoable.

### Non-goals

- Competing with commercial tools on features.
- Accounts, billing, multi-tenant SaaS, private repos in the demo.
- Auto-approving, merging, or fixing code.
- Embedding-based repo retrieval, a database, a job queue.
- A frontend beyond the single demo page.

## 4. Users

| Persona | Need | How they use it |
|---|---|---|
| **Recruiter or hiring manager** | Judge the project quickly | Runs the demo, skims the README results table |
| **Technical interviewer** | Probe depth | Reads the architecture doc and eval methodology |
| **Developer (you, dogfooding)** | A second opinion on a PR | Adds the Action to a repo and reads the comments |

## 5. Requirements

**P0** must ship in v1. **P1** ships if it stays simple.

### Review engine

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Fetch PR metadata and diff from the GitHub API | P0 |
| FR-2 | Filter noise: lockfiles, generated, minified, vendored, binary files | P0 |
| FR-3 | Enforce size limits; if over, review a prioritized subset and say so | P0 |
| FR-4 | Give diff lines stable IDs before prompting so the model cites real lines | P0 |
| FR-5 | Call Gemini with a schema and receive structured findings | P0 |
| FR-6 | Validate every finding against the real diff; drop invalid ones | P0 |
| FR-7 | Rank, apply a confidence threshold, cap findings per PR (default 8) | P0 |
| FR-8 | Verification node in the LangGraph workflow that tries to refute each finding | P0 |
| FR-9 | Record tokens, estimated cost, and latency for each review | P0 |
| FR-10 | Treat PR text and code as untrusted input | P0 |

### GitHub Action

| ID | Requirement | Priority |
|---|---|---|
| FR-20 | Run on `pull_request` and post one review with inline comments and a summary | P0 |
| FR-21 | No duplicate review for the same head commit | P0 |

### Demo page

| ID | Requirement | Priority |
|---|---|---|
| FR-30 | Paste a public PR URL, see streamed progress, then results | P0 |
| FR-31 | Diff view with findings shown as margin notes anchored to lines | P0 |
| FR-32 | Summary strip with model, tokens, cost, latency, skipped files | P0 |
| FR-33 | Example PRs served instantly from cache | P0 |
| FR-34 | Daily budget cap, diff-size cap, public repos only | P0 |
| FR-35 | Cache results by (repo, PR, head SHA, prompt version) | P0 |
| FR-36 | Light and dark theme following the system setting | P1 |

### Evaluation

| ID | Requirement | Priority |
|---|---|---|
| FR-40 | 30 labeled PRs, including clean PRs with no issues | P0 |
| FR-41 | Scoring script: precision, recall, F1, clean-PR false-positive rate | P0 |
| FR-42 | Save each run with git SHA, prompt version, and model; compare two runs | P0 |
| FR-43 | Results table in the README | P0 |

## 6. Non-functional requirements

| Area | Target |
|---|---|
| Latency | Typical PR (under 400 changed lines): p50 under 25s, p95 under 60s. Report real numbers |
| Cost | Under $0.02 per typical review. Report the real figure |
| Reliability | Retry on Gemini and GitHub transient errors; a failed review never posts partial output |
| Security | Secrets server-side only; model output can never approve, merge, or push; secrets in diffs redacted from logs and comments |
| Accessibility | Keyboard usable, visible focus, AA contrast, reduced motion respected |
| Reproducibility | Prompts versioned; model version pinned; eval runs record their config |

## 7. Success metrics

These are targets, not promises. The README reports whatever the real results are.

| Metric | Baseline (no verify) | Target (with verify) |
|---|---|---|
| Precision | Measured | Noticeably higher than baseline |
| Recall | Measured | Not much lower than baseline |
| Comments per PR | Measured | 8 or fewer |
| Cost per review | Measured | Under $0.02 |
| Demo time to first result | n/a | Under 30s (cached examples under 1s) |

Portfolio outcomes: live demo link, README results table, demo GIF, and a "what did not work" section.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Model invents line numbers | Stable line IDs in the prompt; validate every reference; drop anything that does not map |
| Noisy comments | Confidence threshold, comment cap, verify node, precision tracked from the start |
| Labeling 30 PRs is slow and manual | Take labels from existing human review comments and fix commits; cut to 20 PRs if needed |
| Small eval set makes numbers noisy | Report counts alongside percentages; do not overclaim |
| Demo abused | Daily budget cap, size cap, cached examples, public repos only |
| Prompt injection via PR content | Data framing, no tools, schema-only output, output only ever becomes comments |
| Gemini model or quota changes | Pin the model; rerun the eval after any change; fall back to cached examples |
| Scope creep | Phase exit criteria and cut lines in `phases.md` |

## 9. Open questions

1. Which 3-4 Python open-source repos supply the eval PRs?
2. Which Gemini model balances cost and quality? Verify current model IDs and pricing, then decide from the eval.
3. Where to host the demo (Fly.io, Render, or Railway)?
4. Final product name.

## 10. Later (not v1)

Langfuse or LangSmith tracing, GitHub App with webhooks, incremental review on new commits, per-repo rules file, comparing two Gemini models on cost versus quality.

## 11. Related documents

- `architecture.md`: engine, LangGraph workflow, API, eval design
- `design.md`: demo page design
- `phases.md`: build order, tasks, exit criteria
