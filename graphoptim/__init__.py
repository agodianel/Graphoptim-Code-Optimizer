"""
GraphOptim — AI Code Structural Optimizer

A graph-theoretic optimizer for AI-generated Python code.
Parses code into weighted graph representations and applies
graph-theoretic optimization algorithms to detect and fix
structural inefficiencies that rule-based linters cannot catch.

Usage:
    import graphoptim as go

    # Analyze a single function
    report = go.analyze(source_code)
    print(report.score)
    print(report.summary())

    # Optimize code
    optimized = go.optimize(source_code)

    # Analyze a file
    file_report = go.analyze_file("mymodule.py")

    # Optimize a file (preview only)
    go.optimize_file("mymodule.py")

    # Optimize in-place
    go.optimize_file("mymodule.py", inplace=True)
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "GraphOptim Contributors"

import os
import shutil
from pathlib import Path
from typing import Optional

from graphoptim.analyzer.reporter import (
    FileReport,
    FunctionReport,
    analyze_source,
)
from graphoptim.config import AnalyzeConfig, OptimizeConfig
from graphoptim.optimizer.rewriter import optimize_source


def analyze(
    source_code: str,
    filename: str = "<string>",
    config: Optional[AnalyzeConfig] = None,
) -> FileReport:
    """
    Analyze Python source code for structural inefficiencies.

    Args:
        source_code: Python source code string.
        filename: Name of the source file (for reporting).
        config: Optional analysis configuration.

    Returns:
        FileReport containing analysis results.

    Example:
        >>> import graphoptim as go
        >>> report = go.analyze("def foo(x): return x + 1")
        >>> print(report.total_score)
        100
    """
    cfg = config or AnalyzeConfig()
    return analyze_source(
        source_code,
        filename=filename,
        bottleneck_threshold=cfg.bottleneck_threshold,
        max_chain_depth=cfg.max_chain_depth,
    )


def optimize(
    source_code: str,
    passes: Optional[list[str]] = None,
    budget: Optional[dict] = None,
) -> str:
    """
    Optimize Python source code by applying graph-theoretic optimization passes.

    Returns improved source code without modifying any files.

    Args:
        source_code: Python source code string.
        passes: Optional list of specific pass names to apply.
                Available: "dead_code", "path_shortener", "centrality".
                If None, uses knapsack selection to choose optimal passes.
        budget: Optional budget constraints dict:
                - max_changes: Maximum number of changes (int)
                - min_improvement: Minimum improvement threshold (float)

    Returns:
        Optimized source code string.

    Example:
        >>> import graphoptim as go
        >>> code = '''
        ... def foo(x):
        ...     if x > 0:
        ...         return x
        ...     return -x
        ...     print("dead code")
        ... '''
        >>> optimized = go.optimize(code, passes=["dead_code"])
        >>> assert "dead code" not in optimized
    """
    return optimize_source(source_code, passes=passes, budget=budget)


def analyze_file(
    filepath: str,
    config: Optional[AnalyzeConfig] = None,
) -> FileReport:
    """
    Analyze a Python file for structural inefficiencies.

    Args:
        filepath: Path to the Python file.
        config: Optional analysis configuration.

    Returns:
        FileReport containing analysis results.

    Example:
        >>> import graphoptim as go
        >>> report = go.analyze_file("mymodule.py")
        >>> for func in report.functions:
        ...     print(func.function_name, func.score)
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if not path.suffix == ".py":
        raise ValueError(f"Not a Python file: {filepath}")

    source_code = path.read_text(encoding="utf-8")
    return analyze(source_code, filename=str(path), config=config)


def optimize_file(
    filepath: str,
    inplace: bool = False,
    output: Optional[str] = None,
    passes: Optional[list[str]] = None,
    budget: Optional[dict] = None,
) -> str:
    """
    Optimize a Python file.

    By default, returns the optimized code without modifying the file.
    Use inplace=True to modify the file directly (creates .bak backup).

    Args:
        filepath: Path to the Python file.
        inplace: If True, modify the file in-place (creates .bak backup).
        output: Optional output file path.
        passes: Optional list of specific pass names.
        budget: Optional budget constraints.

    Returns:
        Optimized source code string.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    source_code = path.read_text(encoding="utf-8")
    optimized = optimize(source_code, passes=passes, budget=budget)

    if inplace:
        # Create backup
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        path.write_text(optimized, encoding="utf-8")
    elif output:
        Path(output).write_text(optimized, encoding="utf-8")

    return optimized


def analyze_project(
    directory: str,
    config: Optional[AnalyzeConfig] = None,
    exclude: Optional[list[str]] = None,
) -> list[FileReport]:
    """
    Analyze all Python files in a directory.

    Args:
        directory: Path to the directory.
        config: Optional analysis configuration.
        exclude: Optional list of glob patterns to exclude.

    Returns:
        List of FileReport objects, one per file.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    exclude_patterns = exclude or [
        "__pycache__", ".venv", "venv", ".git", "node_modules",
        "*.egg-info", "dist", "build",
    ]

    reports = []
    for py_file in dir_path.rglob("*.py"):
        # Check exclusions
        skip = False
        for pattern in exclude_patterns:
            if pattern in str(py_file):
                skip = True
                break
        if skip:
            continue

        try:
            report = analyze_file(str(py_file), config=config)
            reports.append(report)
        except Exception:
            # Skip files that can't be analyzed
            continue

    return reports


def optimize_project(
    directory: str,
    output_dir: Optional[str] = None,
    passes: Optional[list[str]] = None,
    budget: Optional[dict] = None,
) -> int:
    """
    Optimize all Python files in a directory.

    Args:
        directory: Path to the source directory.
        output_dir: Optional output directory. If None, uses dry-run mode.
        passes: Optional list of specific pass names.
        budget: Optional budget constraints.

    Returns:
        Number of files optimized.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

    count = 0
    for py_file in dir_path.rglob("*.py"):
        if any(
            x in str(py_file)
            for x in ["__pycache__", ".venv", "venv", ".git"]
        ):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            optimized = optimize(source, passes=passes, budget=budget)

            if output_dir:
                # Preserve directory structure
                relative = py_file.relative_to(dir_path)
                out_file = Path(output_dir) / relative
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(optimized, encoding="utf-8")

            count += 1
        except Exception:
            continue

    return count
