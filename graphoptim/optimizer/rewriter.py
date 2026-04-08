"""
Code rewriter for GraphOptim.

Applies AST transformations back to source code, preserving
comments, docstrings, and formatting as much as possible.
"""

from __future__ import annotations

import ast
import re
from typing import Optional

from graphoptim.optimizer.passes.dead_code import DeadCodePass
from graphoptim.optimizer.passes.path_shortener import PathShortenerPass
from graphoptim.optimizer.passes.centrality import CentralityPass
from graphoptim.optimizer.passes.knapsack import KnapsackSelector, PassInfo


# Registry of available passes
PASS_REGISTRY: dict[str, type] = {
    "dead_code": DeadCodePass,
    "path_shortener": PathShortenerPass,
    "centrality": CentralityPass,
}


def optimize_source(
    source_code: str,
    passes: Optional[list[str]] = None,
    budget: Optional[dict] = None,
) -> str:
    """
    Optimize Python source code by applying selected optimization passes.

    This is the main optimization entry point. It:
    1. Detects issues using all available passes
    2. Uses knapsack selection to choose optimal passes within budget
    3. Applies fixes sequentially
    4. Validates output is syntactically correct

    Args:
        source_code: Python source code string.
        passes: Optional list of specific pass names to apply.
                If None, uses knapsack selection.
        budget: Optional budget constraints:
                - max_changes: Maximum number of changes
                - min_improvement: Minimum improvement threshold

    Returns:
        Optimized source code string.

    Raises:
        ValueError: If an unknown pass name is specified.
    """
    if passes:
        # Explicit pass selection
        for name in passes:
            if name not in PASS_REGISTRY:
                raise ValueError(
                    f"Unknown pass '{name}'. Available: {list(PASS_REGISTRY.keys())}"
                )
        selected_passes = [PASS_REGISTRY[name]() for name in passes]
    else:
        # Knapsack-based selection
        selected_passes = _select_passes_auto(source_code, budget)

    # Apply passes sequentially
    optimized = source_code
    for pass_obj in selected_passes:
        try:
            result = pass_obj.fix(optimized)
            # Validate the result is syntactically valid
            ast.parse(result)
            optimized = result
        except SyntaxError:
            # If a pass produces invalid code, skip it
            continue
        except Exception:
            # Graceful degradation — skip failing passes
            continue

    # Final validation
    try:
        ast.parse(optimized)
    except SyntaxError:
        # If the final result is invalid, return original
        return source_code

    # Post-process for readability
    optimized = _post_process(optimized)

    return optimized


def _select_passes_auto(
    source_code: str, budget: Optional[dict] = None
) -> list:
    """Automatically select passes using knapsack."""
    budget_value = 0.6
    if budget and "max_changes" in budget:
        budget_value = min(budget["max_changes"] * 0.1, 1.0)

    # Initialize and detect with all passes
    pass_infos = []
    pass_objects = {}

    for name, cls in PASS_REGISTRY.items():
        pass_obj = cls()
        findings = pass_obj.detect(source_code)

        if findings:
            info = PassInfo(
                name=name,
                cost=pass_obj.cost,
                benefit=pass_obj.benefit,
                pass_obj=pass_obj,
            )
            pass_infos.append(info)
            pass_objects[name] = pass_obj

    if not pass_infos:
        return []

    # Run knapsack selection
    selector = KnapsackSelector(budget=budget_value)
    result = selector.select(pass_infos)

    # Return the actual pass objects in order
    selected = []
    for pi in result.selected_passes:
        if pi.name in pass_objects:
            selected.append(pass_objects[pi.name])

    return selected


def _post_process(code: str) -> str:
    """
    Post-process optimized code for readability.

    ast.unparse() produces valid but sometimes ugly code.
    This function cleans it up.
    """
    lines = code.splitlines()
    processed = []

    for line in lines:
        # Normalize excessive whitespace
        if line.strip():
            processed.append(line)
        else:
            # Keep at most one blank line
            if processed and processed[-1].strip():
                processed.append("")

    # Ensure trailing newline
    result = "\n".join(processed)
    if not result.endswith("\n"):
        result += "\n"

    return result
