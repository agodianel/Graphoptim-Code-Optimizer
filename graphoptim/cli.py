"""
CLI interface for GraphOptim.

Provides command-line access to all GraphOptim functionality:
- analyze: Read-only code inspection
- optimize: Apply optimization passes
- benchmark: Run the empirical benchmark study
- config: Show/set configuration
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="graphoptim")
def main() -> None:
    """GraphOptim — AI Code Structural Optimizer.

    Graph-theoretic optimizer for AI-generated Python code.
    Detects and fixes structural inefficiencies that rule-based
    linters cannot catch.
    """
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--output", "-o", type=click.Path(), help="Output report to file")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.option(
    "--threshold",
    type=float,
    default=0.7,
    help="Betweenness centrality threshold",
)
def analyze(
    path: str,
    verbose: bool,
    output: Optional[str],
    output_format: str,
    threshold: float,
) -> None:
    """Analyze Python code for structural inefficiencies.

    PATH can be a single Python file or a directory.
    """
    target = Path(path)

    if target.is_file():
        _analyze_file(target, verbose, output, output_format, threshold)
    elif target.is_dir():
        _analyze_directory(target, verbose, output, output_format, threshold)
    else:
        console.print(f"[red]Error: '{path}' is not a valid file or directory[/red]")
        sys.exit(1)


def _analyze_file(
    filepath: Path,
    verbose: bool,
    output: Optional[str],
    output_format: str,
    threshold: float,
) -> None:
    """Analyze a single Python file."""
    import graphoptim as go
    from graphoptim.config import AnalyzeConfig

    config = AnalyzeConfig(
        bottleneck_threshold=threshold,
        verbose=verbose,
    )

    try:
        report = go.analyze_file(str(filepath), config=config)
    except Exception as e:
        console.print(f"[red]Error analyzing {filepath}: {e}[/red]")
        sys.exit(1)

    if output_format == "json":
        result = report.to_json()
        if output:
            Path(output).write_text(result, encoding="utf-8")
            console.print(f"[green]Report saved to {output}[/green]")
        else:
            console.print(result)
        return

    # Rich text output
    _print_file_report(report, verbose)

    if output:
        Path(output).write_text(report.summary(), encoding="utf-8")
        console.print(f"\n[dim]Report saved to {output}[/dim]")


def _analyze_directory(
    dirpath: Path,
    verbose: bool,
    output: Optional[str],
    output_format: str,
    threshold: float,
) -> None:
    """Analyze all Python files in a directory."""
    import graphoptim as go
    from graphoptim.config import AnalyzeConfig

    config = AnalyzeConfig(
        bottleneck_threshold=threshold,
        verbose=verbose,
    )

    with console.status("[bold cyan]Analyzing project...[/bold cyan]"):
        reports = go.analyze_project(str(dirpath), config=config)

    if not reports:
        console.print("[yellow]No Python files found to analyze[/yellow]")
        return

    if output_format == "json":
        result = json.dumps([r.to_dict() for r in reports], indent=2)
        if output:
            Path(output).write_text(result, encoding="utf-8")
        else:
            console.print(result)
        return

    # Summary table
    total_functions = sum(len(r.functions) for r in reports)
    avg_score = (
        round(sum(r.total_score for r in reports) / len(reports)) if reports else 0
    )

    console.print()
    panel = Panel(
        f"[bold]Files analyzed:[/bold] {len(reports)}\n"
        f"[bold]Functions analyzed:[/bold] {total_functions}\n"
        f"[bold]Average score:[/bold] {avg_score}/100",
        title=f"[bold cyan]GraphOptim Analysis — {dirpath}[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)

    # Per-file results
    for report in sorted(reports, key=lambda r: r.total_score):
        if verbose or report.total_score < 80:
            _print_file_report(report, verbose)

    console.print(
        f"\n[dim]Run [bold]graphoptim optimize {dirpath}[/bold] to apply fixes.[/dim]"
    )


def _print_file_report(report, verbose: bool) -> None:
    """Print a rich-formatted file report to the console."""
    score = report.total_score
    if score >= 80:
        score_style = "green"
        icon = "✓"
    elif score >= 60:
        score_style = "yellow"
        icon = "~"
    else:
        score_style = "red"
        icon = "⚠"

    console.print()
    header = Text()
    header.append("GraphOptim Analysis — ", style="bold")
    header.append(report.filepath, style="bold cyan")
    console.print(Panel(header, border_style="cyan"))

    console.print(f"  Functions analyzed: [bold]{len(report.functions)}[/bold]")
    console.print(
        f"  Total optimization score: "
        f"[bold {score_style}]{score}/100[/bold {score_style}] {icon}"
    )
    console.print()

    for func in report.functions:
        f_score = func.score
        if f_score >= 80:
            f_style = "green"
            f_status = "✓ good"
        elif f_score >= 60:
            f_style = "yellow"
            f_status = "~ acceptable"
        else:
            f_style = "red"
            f_status = "⚠ needs attention"

        tree = Tree(
            f"[bold]{func.function_name}()[/bold]"
            f"         score: [{f_style}]{f_score}/100  {f_status}[/{f_style}]"
        )

        cc = func.metrics.cyclomatic_complexity
        if cc > 7:
            tree.add(f"Cyclomatic complexity: [red]{cc}[/red]   (threshold: 7)")
        elif verbose:
            tree.add(f"Cyclomatic complexity: [green]{cc}[/green]")

        if func.dead_nodes:
            dead_lines = [str(d.line) for d in func.dead_nodes if d.line]
            tree.add(
                f"Dead nodes: [yellow]{len(func.dead_nodes)}[/yellow]"
                f"               (unreachable at lines {', '.join(dead_lines)})"
            )

        if func.bottlenecks:
            top = func.bottlenecks[0]
            tree.add(
                f"Betweenness bottleneck: [red]{top.betweenness:.1f}[/red]"
                f" (line {top.line} is critical path bottleneck)"
            )

        if func.deep_chains and verbose:
            for chain in func.deep_chains:
                tree.add(
                    f"Deep chain: depth {chain.depth} "
                    f"(lines {chain.line_start}-{chain.line_end})"
                )

        if func.suggested_passes:
            tree.add(
                f"Suggested passes: [cyan]{', '.join(func.suggested_passes)}[/cyan]"
            )

        if verbose:
            tree.add(
                f"Nodes: {func.metrics.nodes}  "
                f"Edges: {func.metrics.edges}  "
                f"LOC: {func.metrics.lines_of_code}"
            )

        console.print(tree)


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=True, help="Preview only (default)")
@click.option("--diff", "show_diff", is_flag=True, help="Show unified diff of changes")
@click.option("--inplace", is_flag=True, help="Modify file in-place (creates .bak)")
@click.option("--output", "-o", type=click.Path(), help="Output to file")
@click.option(
    "--passes",
    "-p",
    type=str,
    help="Comma-separated list of passes (e.g., dead_code,guard_clause)",
)
@click.option(
    "--budget",
    type=float,
    default=0.6,
    help="Risk budget for pass selection (0.0-1.0)",
)
def optimize(
    path: str,
    dry_run: bool,
    show_diff: bool,
    inplace: bool,
    output: Optional[str],
    passes: Optional[str],
    budget: float,
) -> None:
    """Optimize Python code by applying graph-theoretic passes.

    PATH can be a single Python file or a directory.

    Examples:

        graphoptim optimize myfile.py --diff

        graphoptim optimize myfile.py --inplace

        graphoptim optimize src/ --diff
    """
    import graphoptim as go

    target = Path(path)
    pass_list = passes.split(",") if passes else None
    budget_dict = {"max_changes": int(budget * 10)}

    if target.is_file():
        try:
            source = target.read_text(encoding="utf-8")

            if inplace:
                result = go.optimize_file(
                    str(target),
                    inplace=True,
                    passes=pass_list,
                    budget=budget_dict,
                )
                if show_diff:
                    _print_diff(source, result, str(target))
                console.print(
                    f"[green]✓ Optimized {target} in-place "
                    f"(backup: {target}.bak)[/green]"
                )
            elif output:
                result = go.optimize_file(
                    str(target),
                    output=output,
                    passes=pass_list,
                    budget=budget_dict,
                )
                if show_diff:
                    _print_diff(source, result, str(target))
                console.print(f"[green]✓ Optimized code saved to {output}[/green]")
            elif show_diff:
                # Diff mode — show colored diff and auto-save for review
                result = go.optimize(source, passes=pass_list, budget=budget_dict)
                _print_diff(source, result, str(target))

                if result.strip() != source.strip():
                    out_dir = Path("graphoptimized")
                    out_dir.mkdir(exist_ok=True)
                    out_file = out_dir / f"{target.stem}_optimized{target.suffix}"
                    out_file.write_text(result, encoding="utf-8")
                    console.print(
                        f"\n[bold green]💾 Optimized file automatically saved "
                        f"to: {out_file}[/bold green]"
                    )
            else:
                # Dry run — print full optimized code
                result = go.optimize(source, passes=pass_list, budget=budget_dict)
                console.print(Panel("[bold cyan]Optimized Code (dry run)[/bold cyan]"))
                console.print(result)

            # Show before/after score
            before = go.analyze(source, str(target))
            after = go.analyze(result, str(target))

            if before.total_score != after.total_score:
                console.print(
                    f"\n[bold]Score:[/bold] "
                    f"{before.total_score}/100 → "
                    f"[green]{after.total_score}/100[/green]"
                )
            elif show_diff and source.strip() == result.strip():
                console.print("\n[dim]No changes — code is already optimal.[/dim]")

        except Exception as e:
            console.print(f"[red]Error optimizing {target}: {e}[/red]")
            sys.exit(1)

    elif target.is_dir():
        if show_diff or output or inplace:
            _optimize_directory(
                target, show_diff, inplace, output, pass_list, budget_dict
            )
        else:
            console.print(
                "[yellow]Specify --diff, --output DIR, or --inplace "
                "for directory optimization[/yellow]"
            )
    else:
        console.print(f"[red]Error: '{path}' is not a valid file or directory[/red]")
        sys.exit(1)


def _optimize_directory(
    dirpath: Path,
    show_diff: bool,
    inplace: bool,
    output: Optional[str],
    pass_list: Optional[list[str]],
    budget_dict: dict,
) -> None:
    """Optimize all Python files in a directory."""
    import graphoptim as go

    if output:
        with console.status("[bold cyan]Optimizing project...[/bold cyan]"):
            count = go.optimize_project(
                str(dirpath),
                output_dir=output,
                passes=pass_list,
                budget=budget_dict,
            )
        console.print(f"[green]✓ Optimized {count} files → {output}[/green]")
        return

    # Diff or inplace mode — process file by file
    exclude = [
        "__pycache__",
        ".venv",
        "venv",
        ".git",
        "node_modules",
        ".egg-info",
        "dist",
        "build",
    ]
    files_changed = 0

    for py_file in sorted(dirpath.rglob("*.py")):
        if any(x in str(py_file) for x in exclude):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            result = go.optimize(source, passes=pass_list, budget=budget_dict)

            if source.strip() != result.strip():
                files_changed += 1
                if show_diff:
                    _print_diff(source, result, str(py_file))
                if inplace:
                    import shutil

                    backup = py_file.with_suffix(py_file.suffix + ".bak")
                    shutil.copy2(py_file, backup)
                    py_file.write_text(result, encoding="utf-8")
        except Exception:
            continue

    if files_changed == 0:
        console.print("\n[dim]No changes — all files are already optimal.[/dim]")
    else:
        msg = f"\n[bold]{files_changed} file(s) with suggested changes[/bold]"
        if inplace:
            msg += " [green](applied in-place)[/green]"
        console.print(msg)


def _print_diff(original: str, optimized: str, filepath: str) -> None:
    """Print a colored unified diff between original and optimized code."""
    import difflib

    if original.strip() == optimized.strip():
        return

    original_lines = original.splitlines(keepends=True)
    optimized_lines = optimized.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        optimized_lines,
        fromfile=f"{filepath} (original)",
        tofile=f"{filepath} (optimized)",
        lineterm="",
    )

    console.print()
    console.print(Panel(f"[bold cyan]{filepath}[/bold cyan]", border_style="cyan"))

    for line in diff:
        line = line.rstrip("\n")
        if line.startswith("+++"):
            console.print(f"[bold green]{line}[/bold green]")
        elif line.startswith("---"):
            console.print(f"[bold red]{line}[/bold red]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]")
        else:
            console.print(f"[dim]{line}[/dim]")


@main.command()
@click.option(
    "--samples",
    "-n",
    type=int,
    default=100,
    help="Number of benchmark samples",
)
@click.option(
    "--models",
    "-m",
    type=str,
    default="claude,gpt4o,gemini",
    help="Comma-separated list of models",
)
@click.option(
    "--dataset",
    type=click.Choice(["humaneval", "mbpp", "realworld"]),
    default="humaneval",
    help="Benchmark dataset (realworld = complex multi-function tasks)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="benchmark_results",
    help="Output directory",
)
def benchmark(
    samples: int,
    models: str,
    dataset: str,
    output_dir: str,
) -> None:
    """Run the empirical benchmark study.

    Requires API keys set as environment variables:
    ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
    """
    from graphoptim.benchmark.runner import BenchmarkRunner
    from graphoptim.config import BenchmarkConfig

    model_list = models.split(",")
    config = BenchmarkConfig(
        n_samples=samples,
        dataset=dataset,
        models=model_list,
        output_dir=output_dir,
    )

    available = config.validate()
    if not available:
        console.print(
            "[red]Error: No API keys found in environment.[/red]\n"
            "Set at least one of:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  export OPENAI_API_KEY=sk-...\n"
            "  export GOOGLE_API_KEY=AI..."
        )
        sys.exit(1)

    console.print(
        f"[bold cyan]Running benchmark[/bold cyan]\n"
        f"  Dataset: {dataset}\n"
        f"  Samples: {samples}\n"
        f"  Models: {', '.join(available)}\n"
        f"  Output: {output_dir}"
    )

    runner = BenchmarkRunner(config)

    with console.status("[bold cyan]Running benchmark...[/bold cyan]"):
        results = runner.run()

    results.save(output_dir)
    console.print(f"\n[green]✓ Benchmark complete. Results in {output_dir}/[/green]")
    results.show_summary(console)


@main.command()
@click.argument("action", type=click.Choice(["show", "set"]))
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(action: str, key: Optional[str], value: Optional[str]) -> None:
    """Show or set configuration.

    Examples:
        graphoptim config show
        graphoptim config set anthropic_api_key sk-ant-...
    """
    from graphoptim.config import GraphOptimConfig

    cfg = GraphOptimConfig()

    if action == "show":
        table = Table(title="GraphOptim Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Bottleneck threshold", str(cfg.analyze.bottleneck_threshold))
        table.add_row("CC threshold", str(cfg.analyze.cc_threshold))
        table.add_row("Max chain depth", str(cfg.analyze.max_chain_depth))
        table.add_row("Optimize budget", str(cfg.optimize.budget))
        table.add_row("Dry run", str(cfg.optimize.dry_run))
        table.add_row(
            "Anthropic API key",
            "✓ set" if cfg.benchmark.anthropic_api_key else "✗ not set",
        )
        table.add_row(
            "OpenAI API key",
            "✓ set" if cfg.benchmark.openai_api_key else "✗ not set",
        )
        table.add_row(
            "Google API key",
            "✓ set" if cfg.benchmark.google_api_key else "✗ not set",
        )

        console.print(table)

    elif action == "set":
        if not key or not value:
            console.print("[red]Usage: graphoptim config set KEY VALUE[/red]")
            sys.exit(1)

        # For API keys, suggest environment variables
        if "api_key" in key:
            env_var = key.upper()
            console.print(
                f"[yellow]API keys should be set via environment variables:[/yellow]\n"
                f"  export {env_var}={value}"
            )
        else:
            console.print(
                "[yellow]Runtime configuration is not persisted. "
                "Use environment variables or pass options to commands.[/yellow]"
            )


if __name__ == "__main__":
    main()
