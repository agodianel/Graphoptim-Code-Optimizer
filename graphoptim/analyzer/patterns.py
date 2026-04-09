"""
Pattern detectors for GraphOptim.

Detects structural inefficiencies in Control Flow Graphs:
- Dead nodes (unreachable code blocks)
- Redundant paths (duplicate conditional branches)
- Bottleneck nodes (over-centralized code)
- Deep execution chains
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional

import networkx as nx

from graphoptim.parser.ast_utils import ast_node_hash


@dataclass
class DeadNode:
    """A detected dead (unreachable) code block."""

    node_id: int
    line: Optional[int]
    description: str
    severity: str = "warning"  # "info", "warning", "error"


@dataclass
class RedundantPath:
    """A pair of paths in the CFG that are structurally equivalent."""

    path_a: list[int]
    path_b: list[int]
    fingerprint: str
    line_a: Optional[int]
    line_b: Optional[int]
    description: str


@dataclass
class BottleneckNode:
    """A node with high betweenness centrality — a code bottleneck."""

    node_id: int
    betweenness: float
    line: Optional[int]
    description: str
    suggestion: str


@dataclass
class DeepChain:
    """An unnecessarily deep execution chain."""

    path: list[int]
    depth: int
    line_start: Optional[int]
    line_end: Optional[int]
    description: str


def detect_dead_nodes(cfg: nx.DiGraph) -> list[DeadNode]:
    """
    Detect dead (unreachable) code blocks in a CFG.

    A dead node is one with in-degree=0 that is not the entry node.

    Args:
        cfg: NetworkX DiGraph representing the CFG.

    Returns:
        List of DeadNode objects.
    """
    entry = _find_entry(cfg)
    dead_nodes = []

    for node in cfg.nodes:
        if cfg.in_degree(node) == 0 and node != entry:
            lineno = cfg.nodes[node].get("lineno")
            label = cfg.nodes[node].get("label", "")
            dead_nodes.append(
                DeadNode(
                    node_id=node,
                    line=lineno,
                    description=f"Unreachable code block '{label}' at node {node}",
                    severity="warning",
                )
            )

    return dead_nodes


def detect_redundant_paths(cfg: nx.DiGraph) -> list[RedundantPath]:
    """
    Detect redundant (duplicate) paths in a CFG.

    Two paths are considered redundant if they:
    1. Diverge from the same branch point (a node with out-degree >= 2)
    2. Reconverge at the same target node
    3. Have equivalent intermediate operations (same AST structure)

    This scoped approach avoids the O(N²) all-pairs explosion that
    produces inflated false-positive counts.

    Args:
        cfg: NetworkX DiGraph representing the CFG.

    Returns:
        List of RedundantPath objects.
    """
    redundant = []
    seen_pairs: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()

    # Only compare paths that diverge from actual branch points
    branch_points = [n for n in cfg.nodes if cfg.out_degree(n) >= 2]

    for branch_node in branch_points:
        # Get the immediate successors (diverging branches)
        successors = list(cfg.successors(branch_node))
        if len(successors) < 2:
            continue

        # For each pair of successors, find where they reconverge
        for i in range(len(successors)):
            for j in range(i + 1, len(successors)):
                succ_a = successors[i]
                succ_b = successors[j]

                # Find common reachable nodes (reconvergence points)
                try:
                    reachable_a = nx.descendants(cfg, succ_a)
                    reachable_b = nx.descendants(cfg, succ_b)
                except nx.NetworkXError:
                    continue

                reconvergence = reachable_a & reachable_b
                if not reconvergence:
                    continue

                # Check the shortest paths from each successor to reconvergence
                for target in reconvergence:
                    try:
                        paths_a = list(
                            nx.all_simple_paths(cfg, succ_a, target, cutoff=8)
                        )
                        paths_b = list(
                            nx.all_simple_paths(cfg, succ_b, target, cutoff=8)
                        )
                    except nx.NetworkXError:
                        continue

                    if not paths_a or not paths_b:
                        continue

                    # Compare fingerprints between the branch paths
                    for path_a in paths_a:
                        fp_a = _path_fingerprint(cfg, path_a)
                        if not fp_a:  # Skip empty/unresolvable fingerprints
                            continue
                        for path_b in paths_b:
                            fp_b = _path_fingerprint(cfg, path_b)
                            if not fp_b:
                                continue

                            if fp_a == fp_b and len(path_a) >= 2:
                                # Deduplicate — normalize path pair ordering
                                key_a = tuple(path_a)
                                key_b = tuple(path_b)
                                pair_key = (
                                    (min(key_a, key_b), max(key_a, key_b))
                                )
                                if pair_key in seen_pairs:
                                    continue
                                seen_pairs.add(pair_key)

                                line_a = cfg.nodes[path_a[0]].get("lineno")
                                line_b = cfg.nodes[path_b[0]].get("lineno")
                                redundant.append(
                                    RedundantPath(
                                        path_a=[branch_node] + path_a,
                                        path_b=[branch_node] + path_b,
                                        fingerprint=fp_a,
                                        line_a=line_a,
                                        line_b=line_b,
                                        description=(
                                            f"Branches from node {branch_node} "
                                            f"through {succ_a} and {succ_b} "
                                            f"perform equivalent operations"
                                        ),
                                    )
                                )
                                break  # One match per branch pair is enough
                        else:
                            continue
                        break  # One match per reconvergence point

    return redundant


def detect_bottlenecks(
    cfg: nx.DiGraph, threshold: float = 0.7
) -> list[BottleneckNode]:
    """
    Detect bottleneck nodes with high betweenness centrality.

    A bottleneck is a node that many execution paths must pass through,
    indicating over-centralized code that should be decomposed.

    Args:
        cfg: NetworkX DiGraph representing the CFG.
        threshold: Betweenness centrality threshold (0.0 to 1.0).

    Returns:
        List of BottleneckNode objects.
    """
    if cfg.number_of_nodes() < 3:
        return []

    betweenness = nx.betweenness_centrality(cfg)
    bottlenecks = []

    for node, score in betweenness.items():
        if score >= threshold:
            lineno = cfg.nodes[node].get("lineno")
            label = cfg.nodes[node].get("label", "")
            bottlenecks.append(
                BottleneckNode(
                    node_id=node,
                    betweenness=score,
                    line=lineno,
                    description=(
                        f"Node '{label}' (ID={node}) has betweenness "
                        f"centrality {score:.2f} — it's a bottleneck"
                    ),
                    suggestion=(
                        f"Consider extracting the logic at line {lineno} "
                        f"into a separate helper function to reduce coupling"
                    ),
                )
            )

    return sorted(bottlenecks, key=lambda b: b.betweenness, reverse=True)


def detect_deep_chains(
    cfg: nx.DiGraph, max_depth: int = 8
) -> list[DeepChain]:
    """
    Detect unnecessarily deep execution chains.

    A deep chain is a path through the CFG that is longer than
    the specified threshold, indicating overly nested or sequential code.

    Args:
        cfg: NetworkX DiGraph representing the CFG.
        max_depth: Maximum acceptable chain depth.

    Returns:
        List of DeepChain objects.
    """
    deep_chains = []
    entry = _find_entry(cfg)

    if entry is None:
        return deep_chains

    # Find all paths from entry that exceed max_depth
    try:
        for target in cfg.nodes:
            if target == entry:
                continue
            for path in nx.all_simple_paths(cfg, entry, target, cutoff=max_depth + 5):
                if len(path) > max_depth:
                    line_start = cfg.nodes[path[0]].get("lineno")
                    line_end = cfg.nodes[path[-1]].get("lineno")
                    deep_chains.append(
                        DeepChain(
                            path=path,
                            depth=len(path),
                            line_start=line_start,
                            line_end=line_end,
                            description=(
                                f"Execution chain of depth {len(path)} "
                                f"exceeds threshold {max_depth}"
                            ),
                        )
                    )
                    break  # Only report the first deep path to each target
    except nx.NetworkXError:
        pass

    return deep_chains


def _find_entry(cfg: nx.DiGraph) -> Optional[int]:
    """Find the entry node of a CFG."""
    if nx.is_directed_acyclic_graph(cfg):
        try:
            return next(iter(nx.topological_sort(cfg)))
        except StopIteration:
            return None
    return min(cfg.nodes) if cfg.nodes else None


def _path_fingerprint(cfg: nx.DiGraph, path: list[int]) -> str:
    """
    Compute a structural fingerprint for a path in the CFG.

    Uses the AST structure of statements in each node's block.
    Returns an empty string if the path cannot be reliably fingerprinted
    (avoids false positives from generic label matching).
    """
    parts = []
    has_structural_data = False

    for node_id in path:
        block = cfg.nodes[node_id].get("block")
        if block and hasattr(block, "statements") and block.statements:
            has_structural_data = True
            for stmt in block.statements:
                parts.append(ast_node_hash(stmt))
        else:
            # Use a unique placeholder per node to avoid false matches
            # between different generic nodes like "if_cond" and "if_cond"
            parts.append(f"__node_{node_id}__")

    # Require at least some real structural data to produce a valid fingerprint
    if not has_structural_data:
        return ""

    return "|".join(parts)

