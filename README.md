# ReviewLens - LLM-Powered Code Review Agent

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6F00?style=flat)](https://github.com/langchain-ai/langgraph)
[![Google Gemini](https://img.shields.io/badge/Gemini-3.0_Flash-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **ReviewLens** is an intelligent, high-precision code review agent powered by **LangGraph** and **Google Gemini**. It analyzes code changes across **GitHub Pull Requests**, **individual code files**, **entire folders**, and **repositories** to detect real functional defects, security vulnerabilities, and logic bugs with anchored coordinates and adversarial verification.

---

## Key Capabilities & Features

### 1. Universal Input Resolution
ReviewLens supports virtually every way developers share and review code:
- **GitHub Pull Requests**: Review any public or private pull request (`https://github.com/owner/repo/pull/123`).
- **Upload File(s)**: Directly upload single or multiple source code files (`.py`, `.java`, `.js`, `.ts`, `.cpp`, `.c`, `.go`, `.rs`, `.html`, `.css`, etc.) using the integrated upload dropdown.
- **Upload Entire Folders**: Upload full directories directly in the browser via native folder selection (`webkitdirectory`).
- **GitHub Repositories**: Full repository scans (`https://github.com/owner/repo`).
- **GitHub Blobs & Files**: Specific files at any branch or commit (`https://github.com/owner/repo/blob/main/path/to/file.py`).
- **GitHub Commits & Trees**: Specific commit diffs (`/commit/<sha>`) or tree branches (`/tree/<branch>`).
- **Local Files & Folders**: Point to local filesystem paths (e.g. `src/reviewlens/config.py` or `C:\my-project`).
- **Direct Code Snippets**: Paste raw code directly for instantaneous review.

### 2. Adversarial Verification Pipeline (Precision Over Recall)
Most AI reviewers produce noise and nitpicks. ReviewLens prioritizes **measured precision** through a multi-stage LangGraph workflow:
- **Stable Coordinate Tagging**: Diff lines are assigned immutable coordinates (`F1:L42`, `F1:D10`) before prompting, eliminating hallucinated line numbers.
- **Adversarial Verification Node**: A dedicated verification LLM stage actively attempts to refute each finding against surrounding code context before it is accepted.
- **Clean-PR False Positive Rate: 0.0%**: Eliminates baseless comments on clean code.

```
START ──▶ fetch ──▶ filter ──▶ annotate ──▶ review ──▶ validate ──┬── [verify enabled & findings > 0] ──▶ verify ──┐
                                                                  │                                                │
                                                                  └── [otherwise] ────────────────────────────────┴──▶ finalize ──▶ END
```

### 3. Interactive Modern Web UI
- **Unified Single-Section Input Bar**: Clean, distraction-free input bar with upload icon button, clearable file badges, and universal input.
- **Upload Options Dropdown**: Upload files or entire folders with a single click.
- **Night Sky Meteor Shower Canvas**: Smooth 60 FPS HTML5 Canvas animation featuring twinkling stars and glowing shooting stars (with instant Day/Night theme switcher).
- **Real-Time SSE Streaming**: Live progression across the 7 pipeline stages (*Fetch*, *Filter*, *Annotate*, *Review*, *Validate*, *Verify*, *Finalize*).
- **Severity-Coded Findings**: Anchored cards highlighting `HIGH`, `MEDIUM`, and `LOW` issues with actionable code suggestions.

### 4. Multiple Integration Modes
- **Web Application**: Interactive dashboard served with FastAPI and Server-Sent Events.
- **CLI Utility**: Command-line review tool for terminal workflows (`reviewlens review <target>`).
- **GitHub Action**: Automate reviews directly in CI/CD pull request workflows (`action.yml`).

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Core Workflow Engine** | Python 3.11+, LangGraph, Pydantic v2 |
| **LLM & AI** | Google Gemini (`google-genai` SDK with strict JSON schema validation) |
| **Web API Backend** | FastAPI, Uvicorn, Server-Sent Events (SSE), HTTPX |
| **Frontend UI** | HTML5, Vanilla JavaScript (ES6+), HTML5 Canvas (Meteor Shower Animation), Modern CSS with Glassmorphism |
| **CLI & Tools** | Typer, Rich |
| **Testing & Quality** | Pytest, Pytest-asyncio, Ruff |
| **CI/CD** | GitHub Actions (`action.yml`) |

---

## Benchmark Evaluation Results

Evaluated on the labeled benchmark dataset (`eval/dataset/cases.jsonl`) comparing baseline (single-pass review) against ReviewLens with adversarial verification:

| Metric | Baseline (Single-Pass) | ReviewLens (With Verification) | Delta |
|---|:---:|:---:|:---:|
| **Precision** | 78.6% | **94.1%** | **+15.5%** |
| **Clean-PR False Positive Rate** | 22.2% | **0.0%** | **-22.2%** |
| **F1 Score** | 0.80 | **0.84** | **+0.04** |
| **Comments per PR** | 4.2 | **2.1** | **-50% noise** |
| **Mean Cost per PR** | $0.0008 | $0.0012 | +$0.0004 |
| **p50 Latency** | 1.8s | 2.4s | +0.6s |

---

## Getting Started

### 1. Prerequisites
- Python 3.11 or higher
- A Google Gemini API Key ([Get one here](https://aistudio.google.com/))
- (Optional) A GitHub Personal Access Token (for private repositories or higher rate limits)

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/kishanmishra2133-collab/LLM-Powered-Code-Review-Agent.git
cd LLM-Powered-Code-Review-Agent

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -r requirements-dev.txt
pip install -e .
```

### 3. Environment Configuration
Create a `.env` file in the project root:

```env
# Required: Google Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: GitHub Token for private repos and increased API limits
GITHUB_TOKEN=your_github_token_here

# Cache directory (Default: data/cache)
CACHE_DIR=data/cache
```

### 4. Running the Web Application

Start the local server:
```bash
uvicorn reviewlens.adapters.api:app --reload --port 8000
```
Open your browser at **`http://localhost:8000`** to access the web interface.

### 5. Running the CLI

```bash
# Review a public or private GitHub PR
reviewlens review https://github.com/owner/repo/pull/123

# Review a local file or folder
reviewlens review src/reviewlens/config.py
reviewlens review C:/my-project

# Run evaluation benchmarks
reviewlens eval run --tag baseline
reviewlens eval run --tag verify
```

### 6. Using as a GitHub Action

Add `.github/workflows/code-review.yml` to your target repository:

```yaml
name: Automated Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: kishanmishra2133-collab/LLM-Powered-Code-Review-Agent@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
          verify: "true"
          model: "gemini-3-flash-preview"
```

---

## Project Structure

```
.
├── src/reviewlens/             # Core ReviewLens package
│   ├── adapters/
│   │   ├── api.py              # FastAPI server with SSE streaming
│   │   └── cli.py              # Typer CLI commands
│   ├── clients/
│   │   ├── gemini.py           # Google Gemini client with structured output
│   │   └── github.py           # Authenticated GitHub client (PRs, files, diffs)
│   ├── engine/
│   │   ├── graph.py            # LangGraph workflow definition
│   │   └── stages/             # Fetch, Filter, Annotate, Review, Validate, Verify, Finalize
│   ├── models/                 # Pydantic data schemas
│   ├── resolver.py             # Universal input resolver (PR, file, folder, snippet)
│   ├── cache.py                # Review caching and rate limiting
│   └── config.py               # Pydantic Settings configuration
├── web/                        # Web dashboard static assets
│   ├── index.html              # Single-page UI with unified input bar
│   ├── tokens.css              # Design system tokens (Night & Light themes)
│   ├── base.css                # Base layout & meteor canvas styling
│   ├── app.css                 # Component styles (input bar, dropdown, findings)
│   └── app.js                  # Frontend state, SSE client, meteor shower canvas
├── eval/                       # Benchmark evaluation suite
│   ├── dataset/cases.jsonl     # Labeled PR test cases
│   ├── score.py                # Metrics evaluation (precision, recall, F1)
│   └── run.py                  # Evaluation benchmark runner
├── tests/                      # Pytest unit & integration test suite (41 tests)
├── action.yml                  # GitHub Action definition
├── pyproject.toml              # Build & dependency metadata
└── requirements-dev.txt        # Development dependencies
```

---

## Testing & Verification

Run the full test suite:
```bash
pytest tests/ -v
```

Run code formatting and linting:
```bash
ruff check .
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
