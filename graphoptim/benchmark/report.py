"""
Benchmark report generation for GraphOptim.

Generates statistical reports and visualizations comparing
human-written and LLM-generated code metrics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def generate_plots(
    metrics_df: pd.DataFrame,
    output_dir: str,
) -> list[str]:
    """
    Generate benchmark visualization plots.

    Creates:
    - Box plots comparing metrics per source (human vs LLM models)
    - Bar charts of median values
    - Heatmap of statistical significance

    Args:
        metrics_df: DataFrame with all metrics.
        output_dir: Directory to save plot images.

    Returns:
        List of generated plot file paths.
    """
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []

    sns.set_theme(style="whitegrid", palette="muted")

    metrics = [
        "cyclomatic_complexity",
        "dead_nodes_count",
        "max_betweenness_centrality",
        "lines_of_code",
        "node_edge_ratio",
    ]

    # Filter to available metrics
    available_metrics = [m for m in metrics if m in metrics_df.columns]

    if not available_metrics or "source" not in metrics_df.columns:
        return generated

    # 1. Box plots
    fig, axes = plt.subplots(
        1, len(available_metrics), figsize=(5 * len(available_metrics), 6)
    )
    if len(available_metrics) == 1:
        axes = [axes]

    for ax, metric in zip(axes, available_metrics):
        data = metrics_df[["source", metric]].dropna()
        if not data.empty:
            sns.boxplot(data=data, x="source", y=metric, ax=ax)
            ax.set_title(metric.replace("_", " ").title())
            ax.set_xlabel("")

    plt.tight_layout()
    boxplot_path = str(out / "metrics_boxplots.png")
    plt.savefig(boxplot_path, dpi=150)
    plt.close()
    generated.append(boxplot_path)

    # 2. Median comparison bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    medians = metrics_df.groupby("source")[available_metrics].median()
    medians.plot(kind="bar", ax=ax)
    ax.set_title("Median Metrics by Source")
    ax.set_ylabel("Value")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    bar_path = str(out / "median_comparison.png")
    plt.savefig(bar_path, dpi=150)
    plt.close()
    generated.append(bar_path)

    return generated
