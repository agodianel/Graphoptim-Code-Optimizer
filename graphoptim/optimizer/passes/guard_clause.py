"""
Guard Clause Refactoring pass for GraphOptim.

Detects deeply nested conditional blocks at the start of functions
and refactors them into early-return guard clauses, reducing nesting depth.

This is the most impactful transformation for LLM-generated code,
which tends to handle edge cases by nesting if-checks instead of
using early returns.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import Optional


@dataclass
class GuardClauseFinding:
    """A guard clause refactoring opportunity."""

    function_name: str
    line: Optional[int]
    current_depth: int
    potential_depth: int
    description: str


class GuardClausePass:
    """
    Guard clause refactoring optimization pass.

    Detection: Functions where the body is a single if-statement (or a
    chain of nested if-statements) that wraps the main logic. These can
    be refactored to use early returns, reducing nesting depth.

    Fix: Invert leading if-conditions into guard clauses with early returns,
    flattening the function body.
    """

    name = "guard_clause"
    cost = 0.4  # Medium-low risk — structural change but semantics preserved
    benefit = 0.0  # Set dynamically

    def detect(
        self, source_code: str, func_name: Optional[str] = None
    ) -> list[GuardClauseFinding]:
        """
        Find functions with deeply nested bodies that could use guard clauses.

        Args:
            source_code: Python source code string.
            func_name: Optional function name to analyze.

        Returns:
            List of GuardClauseFinding objects.
        """
        findings = []

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if func_name and node.name != func_name:
                continue

            guardable = self._find_guardable_ifs(node.body)
            if guardable:
                current_depth = self._nesting_depth(node.body)
                potential_depth = max(1, current_depth - len(guardable))

                if current_depth >= 3 and len(guardable) >= 1:
                    findings.append(
                        GuardClauseFinding(
                            function_name=node.name,
                            line=node.lineno,
                            current_depth=current_depth,
                            potential_depth=potential_depth,
                            description=(
                                f"Function '{node.name}' has nesting depth "
                                f"{current_depth}, reducible to ~{potential_depth} "
                                f"with {len(guardable)} guard clause(s)"
                            ),
                        )
                    )

        if findings:
            self.benefit = min(len(findings) * 0.25, 0.8)

        return findings

    def fix(self, source_code: str) -> str:
        """
        Refactor deeply nested if-blocks into guard clauses.

        Args:
            source_code: Python source code string.

        Returns:
            Source code with guard clause refactoring applied.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return source_code

        transformer = _GuardClauseTransformer()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        try:
            return ast.unparse(new_tree)
        except Exception:
            return source_code

    def _find_guardable_ifs(self, body: list[ast.stmt]) -> list[ast.If]:
        """
        Find leading if-statements that can be converted to guard clauses.

        A guardable if-statement:
        1. Is at the start of the function body (after docstring)
        2. Has no else branch, OR the else branch is the "main" logic
        3. Wraps the entire remaining function body
        """
        guardable = []

        # Skip docstring
        stmts = body
        if stmts and isinstance(stmts[0], ast.Expr) and isinstance(
            stmts[0].value, (ast.Constant,)
        ):
            stmts = stmts[1:]

        current = stmts
        while current:
            # Check if the body is a single if-statement that wraps everything
            if (
                len(current) == 1
                and isinstance(current[0], ast.If)
                and not current[0].orelse
            ):
                # Pattern: if cond: <entire body>
                # Can invert to: if not cond: return None; <body>
                guardable.append(current[0])
                current = current[0].body
            elif (
                len(current) >= 1
                and isinstance(current[0], ast.If)
                and not current[0].orelse
                and len(current[0].body) >= 2
                and self._nesting_depth(current[0].body) >= 2
            ):
                # Pattern: if cond: <deep body>; more_stmts
                # Only guard if the if-body is deeply nested
                guardable.append(current[0])
                break
            else:
                break

        return guardable

    def _nesting_depth(self, body: list[ast.stmt]) -> int:
        """Compute the maximum nesting depth of a body."""
        if not body:
            return 0

        max_depth = 0
        for stmt in body:
            depth = self._stmt_depth(stmt)
            max_depth = max(max_depth, depth)

        return max_depth

    def _stmt_depth(self, stmt: ast.stmt) -> int:
        """Compute the nesting depth of a single statement."""
        if isinstance(stmt, ast.If):
            body_depth = self._nesting_depth(stmt.body)
            else_depth = self._nesting_depth(stmt.orelse) if stmt.orelse else 0
            return 1 + max(body_depth, else_depth)
        elif isinstance(stmt, (ast.For, ast.While)):
            return 1 + self._nesting_depth(stmt.body)
        elif isinstance(stmt, ast.With):
            return 1 + self._nesting_depth(stmt.body)
        elif isinstance(stmt, ast.Try):
            depths = [self._nesting_depth(stmt.body)]
            for handler in stmt.handlers:
                depths.append(self._nesting_depth(handler.body))
            if stmt.orelse:
                depths.append(self._nesting_depth(stmt.orelse))
            if stmt.finalbody:
                depths.append(self._nesting_depth(stmt.finalbody))
            return 1 + max(depths)
        return 0


class _GuardClauseTransformer(ast.NodeTransformer):
    """AST transformer that converts nested ifs into guard clauses."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        node.body = self._transform_body(node.body)
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        node.body = self._transform_body(node.body)
        return node

    def _transform_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
        """Transform a function body by extracting guard clauses."""
        # Preserve docstring
        result = []
        stmts = list(body)

        if stmts and isinstance(stmts[0], ast.Expr) and isinstance(
            stmts[0].value, (ast.Constant,)
        ):
            result.append(stmts[0])
            stmts = stmts[1:]

        # Iteratively extract guard clauses
        changed = True
        while changed:
            changed = False
            if (
                len(stmts) == 1
                and isinstance(stmts[0], ast.If)
                and not stmts[0].orelse
            ):
                # Pattern: if cond: <entire body>
                # → if not cond: return None; <body>
                if_node = stmts[0]
                guard = ast.If(
                    test=self._invert_condition(if_node.test),
                    body=[ast.Return(value=ast.Constant(value=None))],
                    orelse=[],
                )
                result.append(guard)
                stmts = if_node.body
                changed = True

        result.extend(stmts)
        return result

    def _invert_condition(self, test: ast.expr) -> ast.expr:
        """Invert a boolean condition."""
        # If it's already a `not x`, just return x
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return test.operand

        # If it's a comparison, try to invert the operator
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            inverse_ops = {
                ast.Eq: ast.NotEq,
                ast.NotEq: ast.Eq,
                ast.Lt: ast.GtE,
                ast.GtE: ast.Lt,
                ast.Gt: ast.LtE,
                ast.LtE: ast.Gt,
                ast.Is: ast.IsNot,
                ast.IsNot: ast.Is,
                ast.In: ast.NotIn,
                ast.NotIn: ast.In,
            }
            op_type = type(test.ops[0])
            if op_type in inverse_ops:
                new_test = copy.deepcopy(test)
                new_test.ops = [inverse_ops[op_type]()]
                return new_test

        # General case: wrap in `not`
        return ast.UnaryOp(op=ast.Not(), operand=test)
