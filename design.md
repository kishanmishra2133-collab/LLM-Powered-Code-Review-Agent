# Design: ReviewLens demo page

Plain HTML, CSS, and JavaScript. No framework, no build step. Simple in structure, deliberate in detail.

## 1. Brief

**Subject:** an AI code reviewer for GitHub pull requests.
**Audience:** a recruiter or engineer with 60 seconds and no context.
**Job of the page:** turn a pasted PR URL into a review the visitor can read, judge, and trust.
**Feeling:** a well-made developer tool. Calm, precise, readable. Closer to a good editor's review pane than a marketing site.

The product's native vocabulary is the **diff**: added and removed lines, hunks, and comments on lines. The design draws from that instead of generic "AI product" styling.

## 2. The one memorable thing

**Findings sit in the margin, tied to the exact line they are about.**

Each finding is a note in a right-hand margin, aligned with its line in the diff and joined to it by a thin rule. Severity shows in the rule's weight and a plain-word label. When a review streams in, notes arrive one by one and settle beside their lines. This is the only animated moment on the page. Everything else is quiet.

It also shows the engineering: line-accurate anchoring is the hard part of the system (see `architecture.md`, section 4.5).

## 3. Design plan

### Color

Cool, paper-like neutrals with two diff hues and one action hue. Not cream, not black with neon.

| Token | Name | Light | Dark | Role |
|---|---|---|---|---|
| `--bg` | Chalk | `#F4F6F8` | `#12161C` | Page |
| `--surface` | Paper | `#FFFFFF` | `#1A2029` | Diff pane, input |
| `--ink` | Slate | `#1C2430` | `#E8ECF1` | Primary text |
| `--ink-2` | Graphite | `#5B6675` | `#9AA6B5` | Secondary text |
| `--line` | Fog | `#DDE2E8` | `#2B3441` | Borders, rules |
| `--accent` | Cobalt | `#2F4FE0` | `#7C93FF` | Primary action, focus |
| `--add`, `--add-bg` | Moss | `#2E7D5B`, `#E6F4EC` | `#5CC79A`, `#15291F` | Added lines |
| `--del`, `--del-bg` | Brick | `#B5443C`, `#FBEAE8` | `#F08A82`, `#2E1917` | Removed lines |
| `--sev-med` | Amber | `#B97A0A` | `#E5A93D` | Medium severity rule |

Severity is never carried by color alone: high, medium, and low also differ by rule thickness (3px, 2px, 1px) and a text label. Added and removed lines carry `+` and `-` marks in the gutter. Keep text pairs at WCAG AA contrast.

### Type

| Role | Family | Fallback |
|---|---|---|
| Interface and headings | **Bricolage Grotesque** | `system-ui, sans-serif` |
| Code and line numbers | **JetBrains Mono** | `ui-monospace, Menlo, monospace` |

Scale (rem): 0.8125, 0.9375, 1, 1.25, 1.75, 2.75. Body 1rem at 1.55 line height; code 0.8125rem at 1.6. Prose measure at most 62ch; finding text at most 56ch. Sentence case everywhere; no all-caps labels.

### Layout

Left-aligned. Landing state is one column; results state is a summary strip above a diff with a margin column.

**Landing**

```
┌──────────────────────────────────────────────────────────┐
│ ReviewLens                                               │
│                                                          │
│  Review any public pull request.                         │
│  Paste a link. Read findings on the exact lines.         │
│                                                          │
│  ┌────────────────────────────────────────┐ ┌──────────┐ │
│  │ https://github.com/owner/repo/pull/123 │ │ Review   │ │
│  └────────────────────────────────────────┘ └──────────┘ │
│                                                          │
│  Or try one:  [ example 1 ]  [ example 2 ]  [ example 3 ]│
│                                                          │
│  ─────────────────────────────────────────────────────── │
│  How it scored on 30 labeled pull requests               │
│  Precision 0.xx   Recall 0.xx   $0.0xx per review        │
│  Baseline and with verification (link to README)         │
└──────────────────────────────────────────────────────────┘
```

The input is the hero. The eval numbers below it are real, taken from the latest saved run, and give the page credibility. Hide that block until the eval exists.

**Results**

```
┌──────────────────────────────────────────────────────────────────────┐
│ ReviewLens   [ github.com/owner/repo/pull/123        ] [Review]      │
├──────────────────────────────────────────────────────────────────────┤
│ Fix pagination offset in list view            owner/repo #123        │
│ 5 findings, 2 files skipped, 4 dropped after checking                │
│ gemini-…, 8.4k tokens, $0.006, 14.2s                                 │
│ [ views.py (3) ] [ utils.py (2) ]                     file chips     │
├───────────────────────────────────────────────────┬──────────────────┤
│  40   40    def list(req):                        │                  │
│  41       -   off = page * size                   │                  │
│       41  +   off = page * size + 1               ├─ ┃ High, bug     │
│  42   42      return q[off:]                      │   Off-by-one:    │
│                                                   │   page 1 skips…  │
└───────────────────────────────────────────────────┴──────────────────┘
```

- **File chips** above the diff switch files and show finding counts. Skipped files sit in a collapsed "Skipped" list with the reason for each.
- **Diff** has dual line-number gutters, `+` and `-` marks, and tinted rows.
- **Margin (about 300px)** holds the notes, each aligned to its line. If two would overlap, the lower one moves down.
- **Summary strip** always shows model, tokens, cost, and latency. Showing this openly is part of the pitch.
- **Under 900px:** the margin goes away and each note appears inline under its line as an indented block with the same left rule.

### Principles

1. The diff is the interface. No decorative panels around it.
2. Structure carries information: rules, weights, and gutters mean something.
3. One moment of motion.
4. Show the work: cost, latency, skipped files, dropped findings.
5. Plain words.

## 4. Progress display

Progress mirrors the LangGraph nodes, so it reflects real work. It is a true sequence, so it is numbered.

```
1  Fetching the pull request        done
2  Filtering generated files        done   (2 skipped)
3  Reading the changes              running
4  Checking findings                waiting
```

After results arrive, the list collapses into a single line in the summary strip.

## 5. Finding note

```
┃ High severity, bug
┃ Off-by-one in pagination
┃ Page 1 now skips the first item because…
┃ Suggested change   [ Copy ]
```

- Rule weight: high 3px, medium 2px, low 1px.
- Titles describe the problem ("Off-by-one in pagination"), not the model's feelings.
- The suggestion row appears only when a concrete suggestion exists.
- Clicking a note highlights its line range; clicking a line with a note scrolls to it.

## 6. States and copy

| State | Copy |
|---|---|
| Empty | "Review any public pull request." "Paste a link. Read findings on the exact lines." |
| Invalid URL | "That doesn't look like a GitHub pull request link. It should end in /pull/ and a number." |
| No findings | "No issues found in the 3 files reviewed. That doesn't prove the code is correct." |
| Too large | "This pull request is large. Reviewed the 12 highest-risk files; 30 were skipped." |
| Private or missing | "Can't read that pull request. It may be private or not exist. Only public repositories work here." |
| Budget used up | "Live reviews are paused for today. The examples below still work." |
| Model unavailable | "The review model didn't respond. Try again." |

Errors say what happened and what to do. They do not apologize. Use the same verb for the same action everywhere ("Review", "Copy", "Try again").

## 7. Motion

- When a `finding` event arrives, its note fades in from 12px above and settles over 240ms. Stagger by 60ms, up to six notes. The connecting rule draws in over the same time.
- Everything else is instant.
- With `prefers-reduced-motion: reduce`, notes appear without movement.

## 8. Accessibility

- Semantic landmarks: `header`, `main`, `article` for the diff, `aside` for notes.
- Render the diff as a real `table`. Each changed row has an `aria-label` such as "added line 41".
- A live region announces stage changes and "Review complete: 5 findings".
- Visible focus ring (2px accent, 2px offset); touch targets at least 40px.
- Theme follows `prefers-color-scheme`. There is no toggle in v1.

## 9. Front-end structure

```
web/
├── index.html
├── css/
│   ├── tokens.css        # variables, light and dark
│   ├── base.css          # reset, type, layout, focus
│   └── app.css           # input, progress, diff, notes, errors
└── js/
    ├── main.js           # boot and wiring
    ├── api.js            # EventSource wrapper
    ├── render.js         # progress, summary, diff, notes, errors
    └── dom.js            # small h() helper, format helpers
```

- ES modules via `<script type="module">`; no bundler, no third-party JS.
- The server sends a structured diff, so the browser never parses unified diff text.
- Insert all dynamic text with `textContent`, never `innerHTML`; diff content is untrusted.
- Position notes from each row's `offsetTop` after render, and recompute on resize with a `ResizeObserver`.
- Fonts: Google Fonts with `font-display: swap`, or self-host the two files.

## 10. Token starter (`tokens.css`)

```css
:root {
  --bg: #F4F6F8;  --surface: #FFFFFF;
  --ink: #1C2430; --ink-2: #5B6675;
  --line: #DDE2E8; --accent: #2F4FE0;

  --add: #2E7D5B; --add-bg: #E6F4EC;
  --del: #B5443C; --del-bg: #FBEAE8;
  --sev-high: #B5443C; --sev-med: #B97A0A; --sev-low: #5B6675;

  --font-ui: "Bricolage Grotesque", system-ui, sans-serif;
  --font-code: "JetBrains Mono", ui-monospace, Menlo, monospace;

  --step--1: 0.8125rem; --step-0: 1rem; --step-1: 1.25rem;
  --step-2: 1.75rem;    --step-3: 2.75rem;

  --space-1: 4px;  --space-2: 8px;  --space-3: 16px;
  --space-4: 24px; --space-5: 40px; --space-6: 64px;

  --radius: 6px;          /* input and buttons */
  --radius-pane: 10px;    /* diff pane only */
  --notes-w: 300px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12161C;  --surface: #1A2029;
    --ink: #E8ECF1; --ink-2: #9AA6B5;
    --line: #2B3441; --accent: #7C93FF;
    --add: #5CC79A; --add-bg: #15291F;
    --del: #F08A82; --del-bg: #2E1917;
    --sev-high: #F08A82; --sev-med: #E5A93D; --sev-low: #9AA6B5;
  }
}
```

No shadows: borders and background steps carry depth. Radii differ by role so nothing reads as a uniform card kit.

## 11. Checklist before shipping

- [ ] Works at 360px, 768px, and 1280px widths
- [ ] Keyboard-only run: submit, read findings, copy a suggestion
- [ ] Reduced motion and both color schemes checked
- [ ] Every error state reachable and worded as in section 6
- [ ] A PR with HTML and script text in its diff renders inertly
- [ ] One decorative thing removed at the end
