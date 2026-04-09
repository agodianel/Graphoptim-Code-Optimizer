"""
AST utility functions for GraphOptim.

Provides helper functions for parsing Python source code, extracting functions,
and computing AST node hashes for comparison.
"""

from __future__ import annotations

import ast
import hashlib
import textwrap
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionInfo:
    """Information about a parsed Python function."""

    name: str
    source: str
    ast_node: ast.FunctionDef | ast.AsyncFunctionDef
    lineno: int
    end_lineno: Optional[int]
    decorators: list[ast.expr] = field(default_factory=list)
    docstring: Optional[str] = None


def parse_source(source_code: str) -> ast.Module:
    """
    Parse Python source code into an AST Module.

    Handles common issues like inconsistent indentation by attempting
    to dedent the source before parsing.

    Args:
        source_code: Python source code string.

    Returns:
        Parsed AST Module node.

    Raises:
        SyntaxError: If the source code cannot be parsed.
    """
    try:
        return ast.parse(source_code)
    except IndentationError:
        # Try dedenting the source
        dedented = textwrap.dedent(source_code)
        return ast.parse(dedented)


def extract_functions(source_code: str) -> list[FunctionInfo]:
    """
    Extract all top-level and nested function definitions from source code.

    Args:
        source_code: Python source code string.

    Returns:
        List of FunctionInfo objects for each function found.
    """
    tree = parse_source(source_code)
    functions = []
    lines = source_code.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Extract function source from line numbers
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else len(lines)
            func_source = "\n".join(lines[start:end])

            # Get docstring
            docstring = ast.get_docstring(node)

            functions.append(
                FunctionInfo(
                    name=node.name,
                    source=func_source,
                    ast_node=node,
                    lineno=node.lineno,
                    end_lineno=node.end_lineno,
                    decorators=node.decorator_list,
                    docstring=docstring,
                )
            )

    return functions


def get_function_by_name(source_code: str, func_name: str) -> Optional[FunctionInfo]:
    """
    Get a specific function by name from source code.

    Args:
        source_code: Python source code string.
        func_name: Name of the function to find.

    Returns:
        FunctionInfo for the function, or None if not found.
    """
    functions = extract_functions(source_code)
    for func in functions:
        if func.name == func_name:
            return func
    return None


def ast_node_hash(node: ast.AST) -> str:
    """
    Compute a structural hash of an AST node.

    This hash ignores variable names and literal values, focusing only on
    the structural shape of the AST. This enables detection of structurally
    equivalent code blocks even when they use different variable names.

    Args:
        node: An AST node.

    Returns:
        Hex digest string representing the structural hash.
    """
    return hashlib.md5(_ast_fingerprint(node).encode()).hexdigest()


def _ast_fingerprint(node: ast.AST) -> str:
    """
    Recursively build a structural fingerprint of an AST node.

    The fingerprint captures the type and structure of nodes but
    ignores specific names and values for comparison purposes.
    """
    if isinstance(node, ast.AST):
        parts = [type(node).__name__]
        for field_name, value in ast.iter_fields(node):
            # Skip name-related fields for structural comparison
            if field_name in ("name", "id", "arg", "attr", "module"):
                parts.append(f"{field_name}=<id>")
            elif field_name in ("n", "s", "value") and isinstance(
                node, (ast.Constant,)
            ):
                parts.append(f"{field_name}=<const>")
            elif isinstance(value, list):
                child_parts = [
                    _ast_fingerprint(child)
                    for child in value
                    if isinstance(child, ast.AST)
                ]
                parts.append(f"{field_name}=[{','.join(child_parts)}]")
            elif isinstance(value, ast.AST):
                parts.append(f"{field_name}={_ast_fingerprint(value)}")
        return f"({' '.join(parts)})"
    return str(type(node).__name__)


def get_operation_weight(node: ast.AST) -> float:
    """
    Estimate the computational weight of an AST node.

    Used to weight CFG edges for critical path analysis.
    I/O operations are weighted heavily, arithmetic is light.

    Args:
        node: An AST node.

    Returns:
        Float weight value (0.1 to 10.0).
    """
    # I/O operations — high cost
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in (
                "read",
                "write",
                "open",
                "close",
                "send",
                "recv",
                "readline",
                "readlines",
                "writelines",
            ):
                return 8.0
            if attr in ("get", "post", "put", "delete", "request"):
                return 10.0
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in ("print", "input", "open"):
                return 5.0
            if name in ("sleep",):
                return 10.0
        return 2.0  # Generic function call

    # Loop constructs — medium-high cost
    if isinstance(node, (ast.For, ast.While)):
        return 5.0

    # Exception handling — medium cost
    if isinstance(node, (ast.Try,)):
        return 3.0

    # Conditionals — low-medium cost
    if isinstance(node, ast.If):
        return 1.5

    # Assignments and basic operations — low cost
    if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        return 0.5

    # Arithmetic — very low cost
    if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare)):
        return 0.2

    # Return/yield — minimal cost
    if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
        return 0.1

    return 1.0  # Default weight


def count_non_blank_lines(source_code: str) -> int:
    """Count non-blank, non-comment lines in source code."""
    count = 0
    for line in source_code.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count
