"""
Constant Folding pass for GraphOptim.

Detects constant arithmetic and string expressions and replaces them
with their evaluated results. LLMs frequently emit expressions like
`timeout = 60 * 60` or `max_size = 1024 * 1024` that can be pre-computed.

This is a very low-risk transformation — the result is mathematically
identical to the original.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Any, Callable, Optional

# Safe binary operators for constant folding
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.BitOr: operator.or_,
    ast.BitAnd: operator.and_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

_SAFE_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
}

# Maximum value to fold — prevent creating absurdly large constants
_MAX_FOLD_VALUE = 10**18
_MAX_STRING_LEN = 1000


@dataclass
class ConstantFoldingFinding:
    """A constant expression that can be folded."""

    line: Optional[int]
    original_expr: str
    folded_value: object
    description: str


class ConstantFoldingPass:
    """
    Constant folding optimization pass.

    Detection: Binary operations, unary operations, and string
    concatenations where all operands are constants.

    Fix: Replace the expression with its evaluated result.
    """

    name = "constant_folding"
    cost = 0.1  # Very low risk — pure computation
    benefit = 0.0  # Set dynamically

    def detect(
        self, source_code: str, func_name: Optional[str] = None
    ) -> list[ConstantFoldingFinding]:
        """
        Find constant expressions that can be folded.

        Args:
            source_code: Python source code string.
            func_name: Optional function name to analyze.

        Returns:
            List of ConstantFoldingFinding objects.
        """
        findings: list[ConstantFoldingFinding] = []

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        detector = _ConstantExprDetector()
        detector.visit(tree)
        findings = detector.findings

        if findings:
            self.benefit = min(len(findings) * 0.05, 0.3)

        return findings

    def fix(self, source_code: str) -> str:
        """
        Fold constant expressions in the source code.

        Args:
            source_code: Python source code string.

        Returns:
            Source code with constant expressions folded.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return source_code

        transformer = _ConstantFolder()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        try:
            return ast.unparse(new_tree)
        except Exception:
            return source_code


class _ConstantExprDetector(ast.NodeVisitor):
    """AST visitor that finds foldable constant expressions."""

    def __init__(self) -> None:
        self.findings: list[ConstantFoldingFinding] = []

    def visit_BinOp(self, node: ast.BinOp) -> None:
        result = _try_fold(node)
        if result is not None and not _is_already_constant(node):
            try:
                original = ast.unparse(node)
            except Exception:
                original = "?"
            self.findings.append(
                ConstantFoldingFinding(
                    line=getattr(node, "lineno", None),
                    original_expr=original,
                    folded_value=result,
                    description=(
                        f"Expression '{original}' can be folded to {result!r}"
                    ),
                )
            )
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        result = _try_fold(node)
        if result is not None and not _is_already_constant(node):
            try:
                original = ast.unparse(node)
            except Exception:
                original = "?"
            self.findings.append(
                ConstantFoldingFinding(
                    line=getattr(node, "lineno", None),
                    original_expr=original,
                    folded_value=result,
                    description=(
                        f"Expression '{original}' can be folded to {result!r}"
                    ),
                )
            )
        self.generic_visit(node)


class _ConstantFolder(ast.NodeTransformer):
    """AST transformer that replaces constant expressions with their values."""

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        # Fold children first (bottom-up)
        self.generic_visit(node)
        result = _try_fold(node)
        if result is not None:
            return ast.Constant(value=result)  # type: ignore[arg-type]
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        self.generic_visit(node)
        result = _try_fold(node)
        if result is not None:
            return ast.Constant(value=result)  # type: ignore[arg-type]
        return node


def _try_fold(node: ast.expr) -> object | None:
    """
    Attempt to evaluate a constant expression.

    Returns the result if successful, None otherwise.
    """
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.BinOp):
        left = _try_fold(node.left)
        right = _try_fold(node.right)

        if left is None or right is None:
            return None

        op_func: Callable[..., Any] | None = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            return None

        try:
            result = op_func(left, right)
        except (ZeroDivisionError, OverflowError, ValueError, TypeError):
            return None

        # Validate result is within safe bounds
        if isinstance(result, (int, float)):
            if isinstance(result, float) and (
                result != result or result == float("inf") or result == float("-inf")
            ):
                return None  # NaN or Inf
            if abs(result) > _MAX_FOLD_VALUE:
                return None
        elif isinstance(result, str):
            if len(result) > _MAX_STRING_LEN:
                return None
        elif not isinstance(result, (bool, bytes)):
            return None  # Unsupported type

        return result

    if isinstance(node, ast.UnaryOp):
        operand = _try_fold(node.operand)
        if operand is None:
            return None

        unary_op_func: Any = _SAFE_UNARY_OPS.get(type(node.op))
        if unary_op_func is None:
            return None

        try:
            result = unary_op_func(operand)
        except (OverflowError, TypeError):
            return None

        if isinstance(result, (int, float)) and abs(result) > _MAX_FOLD_VALUE:
            return None

        return result

    return None


def _is_already_constant(node: ast.expr) -> bool:
    """Check if a node is already a simple constant (no folding needed)."""
    return isinstance(node, ast.Constant)
