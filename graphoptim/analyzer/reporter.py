"""
Analysis report generator for GraphOptim.

Produces human-readable analysis reports combining metrics and pattern
detection results into a scored assessment of code quality.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from graphoptim.analyzer.metrics import CFGMetrics, extract_cfg_metrics
from graphoptim.analyzer.patterns import (
    BottleneckNode,
    DeadNode,
    DeepChain,
    RedundantPath,
    detect_bottlenecks,
    detect_dead_nodes,
    detect_deep_chains,
    detect_redundant_paths,
)
from graphoptim.parser.ast_utils import extract_functions
from graphoptim.parser.cfg_builder import build_cfg


# Thresholds for scoring
CC_THRESHOLD = 7
DEAD_NODE_PENALTY = 15
BOTTLENECK_PENALTY = 10
DEEP_CHAIN_PENALTY = 8
REDUNDANT_PATH_PENALTY = 12


@dataclass
class FunctionReport:
    """Analysis report for a single function."""

    function_name: str
    lineno: int
    metrics: CFGMetrics
    dead_nodes: list[DeadNode] = field(default_factory=list)
    redundant_paths: list[RedundantPath] = field(default_factory=list)
    bottlenecks: list[BottleneckNode] = field(default_factory=list)
    deep_chains: list[DeepChain] = field(default_factory=list)
    suggested_passes: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        """
        Calculate optimization score (0-100).

        100 = perfect (no issues found)
        0 = severely problematic
        """
        score = 100

        # Penalize high cyclomatic complexity
        if self.metrics.cyclomatic_complexity > CC_THRESHOLD:
            excess = self.metrics.cyclomatic_complexity - CC_THRESHOLD
            score -= min(excess * 5, 30)

        # Penalize dead nodes
        score -= self.metrics.dead_nodes_count * DEAD_NODE_PENALTY

        # Penalize bottlenecks
        score -= len(self.bottlenecks) * BOTTLENECK_PENALTY

        # Penalize deep chains
        score -= len(self.deep_chains) * DEEP_CHAIN_PENALTY

        # Penalize redundant paths
        score -= len(self.redundant_paths) * REDUNDANT_PATH_PENALTY

        return max(0, min(100, score))

    @property
    def status(self) -> str:
        """Get status emoji and label based on score."""
        if self.score >= 80:
            return "✓ good"
        elif self.score >= 60:
            return "~ acceptable"
        else:
            return "⚠ needs attention"

    def summary(self) -> str:
        """Generate a human-readable summary string."""
        lines = [
            f"function: {self.function_name}()"
            f"         score: {self.score}/100  {self.status}",
        ]

        if self.metrics.cyclomatic_complexity > CC_THRESHOLD:
            lines.append(
                f"  ├─ Cyclomatic complexity: {self.metrics.cyclomatic_complexity}"
                f"   (threshold: {CC_THRESHOLD})"
            )

        if self.dead_nodes:
            dead_lines = [str(d.line) for d in self.dead_nodes if d.line]
            lines.append(
                f"  ├─ Dead nodes: {len(self.dead_nodes)}"
                f"               (unreachable at lines {', '.join(dead_lines)})"
            )

        if self.bottlenecks:
            top = self.bottlenecks[0]
            lines.append(
                f"  ├─ Betweenness bottleneck: {top.betweenness:.1f}"
                f" (line {top.line} is critical path bottleneck)"
            )

        if self.suggested_passes:
            lines.append(
                f"  └─ Suggested passes: {', '.join(self.suggested_passes)}"
            )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "function_name": self.function_name,
            "lineno": self.lineno,
            "score": self.score,
            "status": self.status,
            "metrics": self.metrics.to_dict(),
            "dead_nodes_count": len(self.dead_nodes),
            "redundant_paths_count": len(self.redundant_paths),
            "bottlenecks_count": len(self.bottlenecks),
            "deep_chains_count": len(self.deep_chains),
            "suggested_passes": self.suggested_passes,
        }


@dataclass
class FileReport:
    """Analysis report for an entire file."""

    filepath: str
    functions: list[FunctionReport] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        """Average score across all functions."""
        if not self.functions:
            return 100
        return round(sum(f.score for f in self.functions) / len(self.functions))

    def summary(self) -> str:
        """Generate a human-readable summary string."""
        lines = [
            f"GraphOptim Analysis — {self.filepath}",
            "═" * 50,
            f"Functions analyzed: {len(self.functions)}",
            f"Total optimization score: {self.total_score}/100",
            "",
        ]
        for func_report in self.functions:
            lines.append(func_report.summary())
            lines.append("")

        lines.append(
            f"Run `graphoptim optimize {self.filepath}` to apply fixes."
        )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "filepath": self.filepath,
            "total_score": self.total_score,
            "functions": [f.to_dict() for f in self.functions],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def analyze_source(
    source_code: str,
    filename: str = "<string>",
    bottleneck_threshold: float = 0.7,
    max_chain_depth: int = 8,
) -> FileReport:
    """
    Analyze Python source code and produce a comprehensive report.

    This is the core analysis function that:
    1. Extracts all functions from the source
    2. Builds CFG for each function
    3. Extracts metrics
    4. Runs pattern detectors
    5. Computes scores and suggestions

    Args:
        source_code: Python source code string.
        filename: Name of the source file (for reporting).
        bottleneck_threshold: Betweenness centrality threshold.
        max_chain_depth: Maximum acceptable chain depth.

    Returns:
        FileReport containing analysis results for all functions.
    """
    report = FileReport(filepath=filename)
    functions = extract_functions(source_code)

    for func_info in functions:
        try:
            # Extract metrics
            metrics = extract_cfg_metrics(func_info.source, func_info.name)

            # Build CFG for pattern detection
            cfg = build_cfg(func_info.source, func_info.name)

            # Run pattern detectors
            dead_nodes = detect_dead_nodes(cfg)
            redundant_paths = detect_redundant_paths(cfg)
            bottlenecks = detect_bottlenecks(cfg, threshold=bottleneck_threshold)
            deep_chains = detect_deep_chains(cfg, max_depth=max_chain_depth)

            # Determine suggested passes
            suggested = _suggest_passes(
                metrics, dead_nodes, redundant_paths, bottlenecks, deep_chains
            )

            func_report = FunctionReport(
                function_name=func_info.name,
                lineno=func_info.lineno,
                metrics=metrics,
                dead_nodes=dead_nodes,
                redundant_paths=redundant_paths,
                bottlenecks=bottlenecks,
                deep_chains=deep_chains,
                suggested_passes=suggested,
            )
            report.functions.append(func_report)

        except Exception as e:
            # Graceful degradation — if CFG building fails (e.g., for async
            # functions or complex decorators), still try AST-only metrics
            try:
                metrics = _fallback_metrics(func_info.source)
                func_report = FunctionReport(
                    function_name=func_info.name,
                    lineno=func_info.lineno,
                    metrics=metrics,
                )
                report.functions.append(func_report)
            except Exception:
                # Skip completely unparseable functions
                pass

    return report


def _suggest_passes(
    metrics: CFGMetrics,
    dead_nodes: list[DeadNode],
    redundant_paths: list[RedundantPath],
    bottlenecks: list[BottleneckNode],
    deep_chains: list[DeepChain],
) -> list[str]:
    """Determine which optimization passes would be beneficial."""
    suggestions = []

    if dead_nodes:
        suggestions.append("dead_code")

    if redundant_paths:
        suggestions.append("path_shortener")

    if bottlenecks:
        suggestions.append("centrality_split")

    if deep_chains or metrics.cyclomatic_complexity > CC_THRESHOLD:
        suggestions.append("critical_path")

    return suggestions


def _fallback_metrics(source_code: str) -> CFGMetrics:
    """
    Extract basic metrics without CFG (fallback for unparseable functions).

    Uses only radon and line counting.
    """
    from radon.complexity import cc_visit

    cc_results = cc_visit(source_code)
    cc = cc_results[0].complexity if cc_results else 1

    return CFGMetrics(
        nodes=0,
        edges=0,
        cyclomatic_complexity=cc,
        dead_nodes_count=0,
        dead_node_ids=[],
        avg_shortest_path=None,
        cfg_diameter=None,
        max_betweenness_centrality=0.0,
        node_edge_ratio=0.0,
        lines_of_code=count_non_blank_lines(source_code),
    )


def count_non_blank_lines(source_code: str) -> int:
    """Count non-blank, non-comment lines."""
    return sum(
        1 for line in source_code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
