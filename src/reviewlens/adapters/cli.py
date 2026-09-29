"""Command-line interface for ReviewLens."""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from reviewlens.clients.gemini import GeminiClient
from reviewlens.clients.github import GitHubClient
from reviewlens.config import ReviewConfig, Settings
from reviewlens.engine.graph import run_review_workflow

app = typer.Typer(
    name="reviewlens",
    help="ReviewLens: LLM code review agent with measured quality.",
    add_completion=False,
)
eval_app = typer.Typer(help="Evaluation commands for benchmark runs and comparisons.")
app.add_typer(eval_app, name="eval")

console = Console()


@app.command("review")
def review_cmd(
    target: str = typer.Argument(..., help="GitHub URL (PR, repo, file, commit) or local file/folder path"),
    verify: bool = typer.Option(False, "--verify", help="Enable adversarial verification node"),
    model: str = typer.Option("gemini-3-flash-preview", "--model", help="Gemini model ID"),
    file: str | None = typer.Option(None, "--file", "-f", help="Explicit local file path to review"),
    folder: str | None = typer.Option(None, "--folder", "--dir", "-d", help="Explicit local folder path to review"),
) -> None:
    """Run code review on a GitHub PR, repository, single file, local folder, or local file."""
    settings = Settings()
    if not settings.gemini_api_key or settings.gemini_api_key.strip().startswith("your_"):
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY is not set or is a placeholder in .env file.")
        console.print("Please add your Gemini API key to .env: GEMINI_API_KEY=AIzaSy...")
        raise typer.Exit(code=1)

    effective_target = file or folder or target

    github_client = GitHubClient(token=settings.github_token or None)
    gemini_client = GeminiClient(api_key=settings.gemini_api_key, model_id=model)
    config = ReviewConfig(verify=verify, model_id=model)

    try:
        from reviewlens.resolver import resolve_target

        pr_ref, meta, raw_diff = asyncio.run(
            resolve_target(target_input=effective_target, github_client=github_client)
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    console.print(f"[bold blue]Reviewing:[/bold blue] {meta.title} (model: {model}, verify={verify})...")

    async def _run() -> None:
        result = await run_review_workflow(
            pr=pr_ref,
            config=config,
            github_client=github_client,
            gemini_client=gemini_client,
            raw_diff=raw_diff,
            meta=meta,
        )

        if not result.findings:
            console.print("\n[bold green]No issues found![/bold green] The changes look clean.")
        else:
            table = Table(title="ReviewLens Findings", show_lines=True)
            table.add_column("Location", style="cyan", no_wrap=True)
            table.add_column("Severity", style="bold")
            table.add_column("Category")
            table.add_column("Finding")
            table.add_column("Suggestion")

            for f in result.findings:
                loc = f"{f.file}:{f.line}" if not f.end_line else f"{f.file}:{f.line}-{f.end_line}"
                sev_color = "red" if f.severity == "high" else ("yellow" if f.severity == "medium" else "blue")
                sug = f.suggestion or "-"
                table.add_row(
                    loc,
                    f"[{sev_color}]{f.severity.upper()}[/{sev_color}]",
                    f.category,
                    f"[bold]{f.title}[/bold]\n{f.body}",
                    sug,
                )

            console.print(table)

        console.print(f"\n[dim]{result.summary}[/dim]")

    asyncio.run(_run())


@eval_app.command("run")
def eval_run_cmd(
    tag: str = typer.Option("baseline", "--tag", help="Run tag name (e.g. baseline or verify)"),
    model: str = typer.Option("gemini-3-flash-preview", "--model", help="Gemini model ID"),
    dataset: Path = typer.Option(Path("eval/dataset/cases.jsonl"), "--dataset", help="Path to cases.jsonl"),
) -> None:
    """Run benchmark evaluation over labeled dataset."""
    import sys

    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))

    from eval.run import run_evaluation

    console.print(f"[bold blue]Starting eval run: tag='{tag}', model='{model}'...[/bold blue]")
    output_file = run_evaluation(tag=tag, model=model, dataset_path=dataset)
    console.print(f"[bold green]Evaluation complete! Saved to {output_file}[/bold green]")


@eval_app.command("compare")
def eval_compare_cmd(
    run_a: Path = typer.Argument(..., help="Path to first eval run JSON"),
    run_b: Path = typer.Argument(..., help="Path to second eval run JSON"),
) -> None:
    """Compare two evaluation runs and print metric deltas."""
    if not run_a.is_file() or not run_b.is_file():
        console.print("[bold red]Error:[/bold red] Both run files must exist.")
        raise typer.Exit(code=1)

    with open(run_a, encoding="utf-8") as f:
        data_a = json.load(f)
    with open(run_b, encoding="utf-8") as f:
        data_b = json.load(f)

    m_a = data_a.get("metrics", {})
    m_b = data_b.get("metrics", {})

    table = Table(title=f"Eval Comparison: {run_a.stem} vs {run_b.stem}", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column(run_a.stem, justify="right")
    table.add_column(run_b.stem, justify="right")
    table.add_column("Delta", justify="right", style="bold")

    metrics_keys = [
        ("precision", "{:.2%}"),
        ("recall", "{:.2%}"),
        ("f1", "{:.2%}"),
        ("clean_fp_rate", "{:.2%}"),
        ("comments_per_pr", "{:.2f}"),
        ("mean_cost_usd", "${:.4f}"),
        ("p50_latency_ms", "{:.0f}ms"),
    ]

    for key, fmt in metrics_keys:
        val_a = m_a.get(key, 0.0)
        val_b = m_b.get(key, 0.0)
        delta = val_b - val_a
        delta_str = f"+{fmt.format(delta)}" if delta > 0 else fmt.format(delta)
        color = "green" if (delta > 0 and key in ("precision", "f1")) or (delta < 0 and key == "clean_fp_rate") else "white"
        table.add_row(
            key,
            fmt.format(val_a),
            fmt.format(val_b),
            f"[{color}]{delta_str}[/{color}]",
        )

    console.print(table)


if __name__ == "__main__":
    app()
