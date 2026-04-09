"""
Graph metric extraction for GraphOptim.

Extracts the 7 core metrics from a Control Flow Graph:
1. Cyclomatic Complexity (E - N + 2P)
2. Dead Nodes (unreachable blocks)
3. CFG Diameter (longest shortest path)
4. Average Shortest Path
5. Max Betweenness Centrality
6. Node/Edge Ratio
7. Lines of Code
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import networkx as nx
from radon.complexity import cc_visit

from graphoptim.parser.ast_utils import count_non_blank_lines
from graphoptim.parser.cfg_builder import build_cfg


@dataclass
class CFGMetrics:
    """All measurable graph properties of a function's CFG."""

    nodes: int
    edges: int
    cyclomatic_complexity: int
    dead_nodes_count: int
    dead_node_ids: list[int]
    avg_shortest_path: Optional[float]
    cfg_diameter: Optional[int]
    max_betweenness_centrality: float
    node_edge_ratio: float
    lines_of_code: int

    def to_dict(self) -> dict:
        """Convert metrics to a dictionary."""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "dead_nodes_count": self.dead_nodes_count,
            "dead_node_ids": self.dead_node_ids,
            "avg_shortest_path": self.avg_shortest_path,
            "cfg_diameter": self.cfg_diameter,
            "max_betweenness_centrality": self.max_betweenness_centrality,
            "node_edge_ratio": self.node_edge_ratio,
            "lines_of_code": self.lines_of_code,
        }


def extract_cfg_metrics(
    source_code: str, func_name: Optional[str] = None
) -> CFGMetrics:
    """
    Parse source → CFG → weighted DiGraph → extract graph metrics.

    Args:
        source_code: Python source code string.
        func_name: Optional function name to analyze.

    Returns:
        CFGMetrics dataclass with all measurable graph properties.
    """
    # Build CFG
    cfg = build_cfg(source_code, func_name)

    N = cfg.number_of_nodes()
    E = cfg.number_of_edges()

    # McCabe cyclomatic complexity: E - N + 2P (P=1 for single function)
    cc_graph = E - N + 2

    # Try to get radon's CC for cross-validation
    try:
        cc_results = cc_visit(source_code)
        radon_cc = cc_results[0].complexity if cc_results else cc_graph
    except Exception:
        radon_cc = cc_graph

    # Use the more reliable of the two
    cyclomatic_complexity = radon_cc

    # Dead node detection: nodes with in-degree=0 that are not the entry node
    entry_node = _find_entry_node(cfg)
    dead_nodes = [n for n in cfg.nodes if cfg.in_degree(n) == 0 and n != entry_node]

    # Shortest / longest path (critical path)
    avg_path = _safe_avg_shortest_path(cfg)
    diameter = _safe_diameter(cfg)

    # Centrality
    betweenness = nx.betweenness_centrality(cfg)
    max_betweenness = max(betweenness.values()) if betweenness else 0.0

    # Lines of code
    loc = count_non_blank_lines(source_code)

    return CFGMetrics(
        nodes=N,
        edges=E,
        cyclomatic_complexity=cyclomatic_complexity,
        dead_nodes_count=len(dead_nodes),
        dead_node_ids=dead_nodes,
        avg_shortest_path=avg_path,
        cfg_diameter=diameter,
        max_betweenness_centrality=max_betweenness,
        node_edge_ratio=E / N if N > 0 else 0.0,
        lines_of_code=loc,
    )


def _find_entry_node(cfg: nx.DiGraph) -> Optional[int]:
    """
    Find the entry node of a CFG.

    The entry node is determined by:
    1. Topological sort (first node) if the graph is a DAG
    2. Node with the smallest ID (usually 0) otherwise
    """
    if nx.is_directed_acyclic_graph(cfg):
        try:
            return next(iter(nx.topological_sort(cfg)))
        except StopIteration:
            return None

    # For graphs with cycles (loops), use the node with smallest ID
    if cfg.nodes:
        return min(cfg.nodes)
    return None


def _safe_avg_shortest_path(cfg: nx.DiGraph) -> Optional[float]:
    """Safely compute average shortest path length."""
    try:
        if nx.is_strongly_connected(cfg):
            return nx.average_shortest_path_length(cfg)
        # For non-strongly-connected graphs, compute on largest SCC
        sccs = list(nx.strongly_connected_components(cfg))
        if sccs:
            largest_scc = max(sccs, key=len)
            if len(largest_scc) > 1:
                subgraph = cfg.subgraph(largest_scc)
                return nx.average_shortest_path_length(subgraph)
    except Exception:
        pass
    return None


def _safe_diameter(cfg: nx.DiGraph) -> Optional[int]:
    """Safely compute CFG diameter (on undirected version)."""
    try:
        undirected = cfg.to_undirected()
        if nx.is_connected(undirected):
            return nx.diameter(undirected)
        # Use largest connected component
        components = list(nx.connected_components(undirected))
        if components:
            largest = max(components, key=len)
            if len(largest) > 1:
                subgraph = undirected.subgraph(largest)
                return nx.diameter(subgraph)
    except Exception:
        pass
    return None
