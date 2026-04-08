"""
Betweenness Centrality Decomposition pass for GraphOptim.

Detects nodes with high betweenness centrality (bottlenecks) and
suggests extracting their logic into helper functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import networkx as nx

from graphoptim.analyzer.patterns import BottleneckNode, detect_bottlenecks
from graphoptim.parser.cfg_builder import build_cfg


@dataclass
class CentralityFinding:
    """A centrality bottleneck finding with decomposition suggestion."""

    node_id: int
    betweenness: float
    line: Optional[int]
    description: str
    suggestion: str


class CentralityPass:
    """
    Betweenness centrality decomposition pass.

    Detection: Nodes with betweenness_centrality > threshold (default: 0.7).
    These are bottleneck nodes that every execution path passes through,
    indicating over-centralized code.

    Fix: Suggest extracting the bottleneck node's logic into a helper
    function to improve testability and reusability.
    """

    name = "centrality"
    cost = 0.6  # Higher risk — restructuring code flow
    benefit = 0.0  # Set dynamically

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold

    def detect(
        self, source_code: str, func_name: Optional[str] = None
    ) -> list[CentralityFinding]:
        """
        Find bottleneck nodes in the source code.

        Args:
            source_code: Python source code string.
            func_name: Optional function name to analyze.

        Returns:
            List of CentralityFinding objects.
        """
        findings = []

        try:
            cfg = build_cfg(source_code, func_name)
            bottlenecks = detect_bottlenecks(cfg, threshold=self.threshold)

            for bn in bottlenecks:
                findings.append(
                    CentralityFinding(
                        node_id=bn.node_id,
                        betweenness=bn.betweenness,
                        line=bn.line,
                        description=bn.description,
                        suggestion=bn.suggestion,
                    )
                )
        except Exception:
            pass

        if findings:
            self.benefit = min(len(findings) * 0.15, 0.5)

        return findings

    def fix(self, source_code: str) -> str:
        """
        Centrality fix is advisory-only.

        Extracting bottleneck logic requires semantic understanding
        that is beyond safe automated rewriting. This pass returns
        the original code with advisory comments added.

        Args:
            source_code: Python source code string.

        Returns:
            Source code with advisory comments at bottleneck lines.
        """
        findings = self.detect(source_code)
        if not findings:
            return source_code

        lines = source_code.splitlines()
        for finding in sorted(findings, key=lambda f: f.line or 0, reverse=True):
            if finding.line and 0 < finding.line <= len(lines):
                idx = finding.line - 1
                indent = len(lines[idx]) - len(lines[idx].lstrip())
                comment = (
                    f"{' ' * indent}# TODO(graphoptim): Bottleneck detected "
                    f"(betweenness={finding.betweenness:.2f}). "
                    f"Consider extracting this logic into a helper function."
                )
                lines.insert(idx, comment)

        return "\n".join(lines)
