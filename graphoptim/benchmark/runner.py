"""
Benchmark runner for GraphOptim.

Runs the full benchmark pipeline: collect dataset, extract metrics,
run statistical tests, and generate reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console

from graphoptim.analyzer.metrics import extract_cfg_metrics
from graphoptim.benchmark.collector import BenchmarkProblem, DatasetCollector
from graphoptim.config import BenchmarkConfig


@dataclass
class BenchmarkResults:
    """Results of a benchmark run."""

    metrics_df: pd.DataFrame
    statistical_df: pd.DataFrame
    raw_data: list[dict] = field(default_factory=list)

    def save(self, output_dir: str) -> None:
        """Save results to the output directory with per-model subfolders."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # --- Per-model subfolders ---
        if "source" in self.metrics_df.columns:
            models = [s for s in self.metrics_df["source"].unique() if s != "human"]
            for model in models:
                model_dir = out / model
                model_dir.mkdir(parents=True, exist_ok=True)

                # Model-specific metrics
                model_df = self.metrics_df[
                    self.metrics_df["source"].isin([model, "human"])
                ]
                model_df.to_json(model_dir / "metrics.json", orient="records", indent=2)

                # Model-specific raw data
                model_raw = [
                    r for r in self.raw_data if r.get("source") in (model, "human")
                ]
                with open(model_dir / "raw_data.json", "w", encoding="utf-8") as f:
                    json.dump(model_raw, f, indent=2)

                # Model-specific statistical report
                if not self.statistical_df.empty:
                    model_stats = self.statistical_df[
                        self.statistical_df["model"] == model
                    ]
                    model_stats.to_csv(
                        model_dir / "statistical_report.csv", index=False
                    )

                # Model-specific markdown report
                model_report = self._generate_model_report(model)
                (model_dir / "report.md").write_text(model_report, encoding="utf-8")

            # Save human-only metrics in a human/ subfolder
            human_dir = out / "human"
            human_dir.mkdir(parents=True, exist_ok=True)
            human_df = self.metrics_df[self.metrics_df["source"] == "human"]
            human_df.to_json(human_dir / "metrics.json", orient="records", indent=2)

        # --- Top-level aggregate files ---
        self.metrics_df.to_json(out / "all_metrics.json", orient="records", indent=2)
        self.statistical_df.to_csv(out / "statistical_report.csv", index=False)
        report_md = self._generate_report()
        (out / "benchmark_report.md").write_text(report_md, encoding="utf-8")
        with open(out / "raw_data.json", "w", encoding="utf-8") as f:
            json.dump(self.raw_data, f, indent=2)

    def show_summary(self, console: Optional[Console] = None) -> None:
        """Print a summary to the console."""
        if console is None:
            console = Console()

        console.print("\n[bold cyan]Benchmark Summary[/bold cyan]")
        console.print(f"  Total functions analyzed: {len(self.metrics_df)}")

        if not self.statistical_df.empty:
            sig = self.statistical_df[self.statistical_df["significant"]]
            console.print(
                f"  Significant differences found: {len(sig)}/{len(self.statistical_df)}"
            )

            for _, row in sig.iterrows():
                direction = (
                    "higher" if row["llm_median"] > row["human_median"] else "lower"
                )
                console.print(
                    f"    [yellow]{row['model']}[/yellow] {row['metric']}: "
                    f"{direction} (p={row['p_value']:.4f})"
                )

    def _generate_report(self) -> str:
        """Generate a human-readable markdown report."""
        lines = [
            "# GraphOptim Benchmark Report",
            "",
            "## Summary",
            "",
            f"Total functions analyzed: {len(self.metrics_df)}",
            "",
            "## Statistical Analysis",
            "",
            "Comparison of graph-level structural metrics between human-written",
            "and LLM-generated code using Mann-Whitney U tests.",
            "",
        ]

        if not self.statistical_df.empty:
            lines.append(
                "| Metric | Model | Human Median | LLM Median | p-value | Significant |"
            )
            lines.append(
                "|--------|-------|-------------|------------|---------|-------------|"
            )

            for _, row in self.statistical_df.iterrows():
                sig_marker = "✓" if row["significant"] else ""
                lines.append(
                    f"| {row['metric']} | {row['model']} | "
                    f"{row['human_median']:.2f} | {row['llm_median']:.2f} | "
                    f"{row['p_value']:.4f} | {sig_marker} |"
                )

        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                "Significant results (p < 0.05) indicate that LLM-generated code",
                "differs measurably from human-written code in the corresponding",
                "graph-level structural metric.",
                "",
                "---",
                "*Generated by GraphOptim benchmark pipeline*",
            ]
        )

        return "\n".join(lines)

    def _generate_model_report(self, model: str) -> str:
        """Generate a report for a specific model vs human."""
        model_df = self.metrics_df[self.metrics_df["source"] == model]
        human_df = self.metrics_df[self.metrics_df["source"] == "human"]

        model_names = {
            "claude": "Claude Opus 4.6",
            "gpt4o": "GPT-5.2",
            "gemini": "Gemini 3.1 Pro",
        }
        display_name = model_names.get(model, model)

        lines = [
            f"# {display_name} vs Human — Benchmark Report",
            "",
            "## Summary",
            "",
            f"- **Model**: {display_name}",
            f"- **LLM functions analyzed**: {len(model_df)}",
            f"- **Human functions analyzed**: {len(human_df)}",
            "",
        ]

        # Metric comparison table
        metrics = [
            "cyclomatic_complexity",
            "dead_nodes_count",
            "lines_of_code",
            "cfg_diameter",
            "max_betweenness_centrality",
            "node_edge_ratio",
        ]
        available = [m for m in metrics if m in self.metrics_df.columns]

        if available:
            lines.extend(
                [
                    "## Metric Comparison",
                    "",
                    "| Metric | Human (median) | LLM (median) | Δ |",
                    "|--------|---------------|-------------|---|",
                ]
            )
            for metric in available:
                h_med = human_df[metric].median() if metric in human_df else 0
                l_med = model_df[metric].median() if metric in model_df else 0
                delta = l_med - h_med
                arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
                lines.append(
                    f"| {metric} | {h_med:.2f} | {l_med:.2f} | {arrow} {abs(delta):.2f} |"
                )

        # Statistical tests for this model
        if not self.statistical_df.empty:
            model_stats = self.statistical_df[self.statistical_df["model"] == model]
            if not model_stats.empty:
                lines.extend(
                    [
                        "",
                        "## Statistical Tests (Mann-Whitney U)",
                        "",
                        "| Metric | p-value | Significant |",
                        "|--------|---------|-------------|",
                    ]
                )
                for _, row in model_stats.iterrows():
                    sig = "✓ Yes" if row["significant"] else "No"
                    lines.append(f"| {row['metric']} | {row['p_value']:.4f} | {sig} |")

        lines.extend(
            [
                "",
                "---",
                "*Generated by GraphOptim benchmark pipeline*",
            ]
        )
        return "\n".join(lines)


class BenchmarkRunner:
    """
    Runs the complete benchmark pipeline.

    1. Collect dataset (download + LLM solution generation)
    2. Extract CFG metrics for all functions
    3. Run statistical tests
    4. Generate report
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config

    def run(self) -> BenchmarkResults:
        """Run the full benchmark pipeline."""
        # Step 1: Collect dataset
        collector = DatasetCollector(self.config)
        problems = collector.collect()

        # Save raw dataset
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        collector.save_dataset(problems, str(out_dir / "benchmark_dataset.json"))

        # Step 2: Extract metrics
        if self.config.dataset == "realworld":
            all_metrics = self._extract_realworld_metrics(problems)
        else:
            all_metrics = self._extract_humaneval_metrics(problems)

        metrics_df = pd.DataFrame(all_metrics)

        # Step 3: Statistical tests
        statistical_df = self._run_statistical_tests(metrics_df)

        return BenchmarkResults(
            metrics_df=metrics_df,
            statistical_df=statistical_df,
            raw_data=all_metrics,
        )

    def _extract_humaneval_metrics(
        self, problems: list[BenchmarkProblem]
    ) -> list[dict]:
        """Extract metrics for HumanEval/MBPP (human vs LLM comparison)."""
        print(f"\n  Extracting metrics from {len(problems)} problems...")
        all_metrics = []
        for i, problem in enumerate(problems):
            # Human solution — combine prompt + canonical for HumanEval
            human_source = problem.prompt + problem.canonical_solution
            human_metrics = self._safe_extract(human_source, problem.task_id)
            if human_metrics is None:
                human_metrics = self._safe_extract(
                    problem.canonical_solution, problem.task_id
                )
            if human_metrics:
                human_metrics["source"] = "human"
                human_metrics["task_id"] = problem.task_id
                all_metrics.append(human_metrics)

            # LLM solutions
            for model, solution in problem.llm_solutions.items():
                llm_metrics = self._safe_extract(solution, problem.task_id)
                if llm_metrics:
                    llm_metrics["source"] = model
                    llm_metrics["task_id"] = problem.task_id
                    all_metrics.append(llm_metrics)

            if (i + 1) % 25 == 0:
                print(f"    Metrics progress: {i + 1}/{len(problems)}")

        return all_metrics

    def _extract_realworld_metrics(
        self, problems: list[BenchmarkProblem]
    ) -> list[dict]:
        """
        Extract metrics for real-world benchmark (multi-function).

        For each LLM solution:
        1. Extract per-function CFG metrics
        2. Run GraphOptim analyze for patterns and scoring
        3. Run GraphOptim optimize to measure improvement
        """
        import graphoptim as go

        print(f"\n  Extracting real-world metrics from {len(problems)} problems...")
        all_metrics = []

        for i, problem in enumerate(problems):
            for model, solution in problem.llm_solutions.items():
                if solution.startswith("# Error"):
                    continue

                clean = self._clean_source(solution)

                # Run full GraphOptim analysis
                try:
                    report = go.analyze(clean)
                    optimized = go.optimize(clean)

                    # Before/after scores
                    after_report = go.analyze(optimized)

                    entry = {
                        "task_id": problem.task_id,
                        "source": model,
                        "num_functions": len(report.functions),
                        "total_score_before": report.total_score,
                        "total_score_after": after_report.total_score,
                        "score_improvement": (
                            after_report.total_score - report.total_score
                        ),
                        "lines_of_code": len(clean.splitlines()),
                        "lines_after_optimize": len(optimized.splitlines()),
                        "lines_removed": (
                            len(clean.splitlines()) - len(optimized.splitlines())
                        ),
                    }

                    # Aggregate per-function metrics
                    total_cc = 0
                    total_dead = 0
                    total_bottlenecks = 0
                    total_deep_chains = 0
                    total_redundant = 0

                    for func in report.functions:
                        total_cc += func.metrics.cyclomatic_complexity
                        total_dead += len(func.dead_nodes) if func.dead_nodes else 0
                        total_bottlenecks += (
                            len(func.bottlenecks) if func.bottlenecks else 0
                        )
                        total_deep_chains += (
                            len(func.deep_chains) if func.deep_chains else 0
                        )
                        total_redundant += (
                            len(func.redundant_paths) if func.redundant_paths else 0
                        )

                    entry["avg_cyclomatic_complexity"] = total_cc / max(
                        len(report.functions), 1
                    )
                    entry["total_dead_nodes"] = total_dead
                    entry["total_bottlenecks"] = total_bottlenecks
                    entry["total_deep_chains"] = total_deep_chains
                    entry["total_redundant_paths"] = total_redundant
                    entry["patterns_found"] = (
                        total_dead
                        + total_bottlenecks
                        + total_deep_chains
                        + total_redundant
                    )

                    all_metrics.append(entry)

                except Exception as e:
                    print(f"    ⚠ Analysis failed for {model}/{problem.task_id}: {e}")

            if (i + 1) % 5 == 0:
                print(f"    Progress: {i + 1}/{len(problems)}")

        return all_metrics

    def _safe_extract(self, source_code: str, task_id: str) -> dict | None:
        """Safely extract metrics from source code."""
        if not source_code or source_code.startswith("# Error"):
            return None

        try:
            # Clean up the source code (remove markdown fences if present)
            clean = self._clean_source(source_code)
            metrics = extract_cfg_metrics(clean)
            return metrics.to_dict()
        except Exception:
            return None

    def _clean_source(self, source: str) -> str:
        """
        Clean LLM output — extract valid Python from markdown responses.

        Handles:
        - Markdown code fences (```python ... ```)
        - Explanatory text before/after code
        - Multiple code blocks (takes the largest)
        - Truncated output (removes incomplete trailing statements)
        """
        import ast
        import re

        text = source.strip()

        # Strategy 1: Extract code from markdown fences
        # Find all ```python ... ``` blocks (closed fences)
        pattern = r"```(?:python)?\s*\n(.*?)```"
        blocks = re.findall(pattern, text, re.DOTALL)

        if not blocks:
            # Handle truncated output — opening fence but no closing fence
            pattern_open = r"```(?:python)?\s*\n(.*)"
            blocks = re.findall(pattern_open, text, re.DOTALL)

        if blocks:
            # Use the largest code block
            code = max(blocks, key=len).strip()
        else:
            # No fences — try stripping non-code lines from start/end
            lines = text.splitlines()

            # Remove leading non-code lines (explanations)
            start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (
                    stripped.startswith(
                        ("import ", "from ", "class ", "def ", "#", "@", '"""')
                    )
                    or stripped == ""
                    or stripped.startswith(("'''", "logging", "__"))
                ):
                    start = i
                    break

            code = "\n".join(lines[start:])

        # Strategy 2: If truncated, trim until it parses
        # Try parsing as-is first
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            pass

        # Remove trailing incomplete lines until it parses
        lines = code.splitlines()
        for trim in range(1, min(30, len(lines))):
            trimmed = "\n".join(lines[:-trim])
            if not trimmed.strip():
                break
            try:
                ast.parse(trimmed)
                return trimmed
            except SyntaxError:
                continue

        # Final fallback: return what we have (will fail at analysis)
        return code

    def _run_statistical_tests(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run Mann-Whitney U tests between human and each LLM group."""
        from scipy.stats import mannwhitneyu

        metrics = [
            "cyclomatic_complexity",
            "dead_nodes_count",
            "avg_shortest_path",
            "cfg_diameter",
            "max_betweenness_centrality",
            "lines_of_code",
        ]

        results: list[dict] = []
        if "source" not in df.columns:
            return pd.DataFrame(results)

        human = df[df["source"] == "human"]

        for metric in metrics:
            if metric not in df.columns:
                continue

            human_vals = human[metric].dropna()
            if human_vals.empty:
                continue

            for model in ["claude", "gpt4o", "gemini"]:
                llm_vals = df[df["source"] == model][metric].dropna()
                if llm_vals.empty:
                    continue

                try:
                    stat, p = mannwhitneyu(
                        human_vals, llm_vals, alternative="two-sided"
                    )
                    results.append(
                        {
                            "metric": metric,
                            "model": model,
                            "human_median": human_vals.median(),
                            "llm_median": llm_vals.median(),
                            "u_statistic": stat,
                            "p_value": p,
                            "significant": p < 0.05,
                        }
                    )
                except Exception:
                    continue

        return pd.DataFrame(results)
