"""
Unused Variable Elimination pass for GraphOptim.

Detects variables that are assigned but never read, and removes
the assignments when it's safe to do so (i.e., the right-hand side
has no side effects).

This catches a common LLM pattern where variables are assigned for
"clarity" or "debugging" but never actually used downstream.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional


@dataclass
class UnusedVariableFinding:
    """An unused variable finding."""

    variable_name: str
    line: Optional[int]
    is_safe_to_remove: bool
    description: str


class UnusedVariablePass:
    """
    Unused variable elimination optimization pass.

    Detection: Variables that are assigned (via =, augmented assignment,
    or named expression) but never referenced anywhere in the function.

    Fix: Remove the assignment statement entirely if the RHS is a pure
    expression (no function calls, attribute access, or subscript
    operations that could have side effects).
    """

    name = "unused_variable"
    cost = 0.3  # Low-medium risk — safe when RHS is side-effect-free
    benefit = 0.0  # Set dynamically

    def detect(
        self, source_code: str, func_name: Optional[str] = None
    ) -> list[UnusedVariableFinding]:
        """
        Find unused variables in the source code.

        Args:
            source_code: Python source code string.
            func_name: Optional function name to analyze.

        Returns:
            List of UnusedVariableFinding objects.
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

            func_findings = self._analyze_function(node)
            findings.extend(func_findings)

        if findings:
            self.benefit = min(len(findings) * 0.1, 0.5)

        return findings

    def fix(self, source_code: str) -> str:
        """
        Remove unused variable assignments where safe.

        Args:
            source_code: Python source code string.

        Returns:
            Source code with safe unused variable assignments removed.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return source_code

        transformer = _UnusedVariableRemover()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        try:
            return ast.unparse(new_tree)
        except Exception:
            return source_code

    def _analyze_function(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[UnusedVariableFinding]:
        """Analyze a single function for unused variables."""
        findings = []

        # Collect all assigned names and their assignment nodes
        assignments = _collect_assignments(func_node)
        # Collect all referenced names (reads)
        references = _collect_references(func_node)

        # Find variables that are assigned but never referenced
        for var_name, assign_info in assignments.items():
            if var_name.startswith("_"):
                # Convention: underscore-prefixed vars are intentionally unused
                continue
            if var_name in references:
                continue

            is_safe = _is_pure_expression(assign_info["rhs"])

            findings.append(
                UnusedVariableFinding(
                    variable_name=var_name,
                    line=assign_info["line"],
                    is_safe_to_remove=is_safe,
                    description=(
                        f"Variable '{var_name}' is assigned at line "
                        f"{assign_info['line']} but never used"
                        + ("" if is_safe else " (RHS may have side effects)")
                    ),
                )
            )

        return findings


def _collect_assignments(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, dict]:
    """
    Collect all simple variable assignments in a function.

    Returns a dict mapping variable name to assignment info.
    Only tracks simple name assignments (not tuple unpacking, attribute
    assignment, or subscript assignment).
    """
    assignments: dict[str, dict] = {}

    # Don't count function arguments as "assignments"
    arg_names = set()
    for arg in func_node.args.args + func_node.args.posonlyargs + func_node.args.kwonlyargs:
        arg_names.add(arg.arg)
    if func_node.args.vararg:
        arg_names.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        arg_names.add(func_node.args.kwarg.arg)

    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in arg_names:
                    assignments[target.id] = {
                        "line": node.lineno,
                        "rhs": node.value,
                        "node": node,
                    }
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.value is not None
                and node.target.id not in arg_names
            ):
                assignments[node.target.id] = {
                    "line": node.lineno,
                    "rhs": node.value,
                    "node": node,
                }

    return assignments


def _collect_references(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """
    Collect all name references (reads) in a function body.

    Excludes the left-hand side of assignments — we only want reads.
    """
    references: set[str] = set()

    for node in ast.walk(func_node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            references.add(node.id)
        # Also check attribute access (e.g., x.method() means x is used)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if isinstance(node.value, ast.Name):
                references.add(node.value.id)
        # Subscript access (e.g., x[0] means x is used)
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            if isinstance(node.value, ast.Name):
                references.add(node.value.id)
        # f-strings reference names
        elif isinstance(node, ast.JoinedStr):
            for val in node.values:
                if isinstance(val, ast.FormattedValue) and isinstance(
                    val.value, ast.Name
                ):
                    references.add(val.value.id)

    return references


def _is_pure_expression(node: ast.expr) -> bool:
    """
    Check if an expression is pure (no side effects).

    Pure expressions are safe to remove if their result is unused.
    """
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        # Check all elements are pure
        if isinstance(node, ast.Dict):
            return all(
                _is_pure_expression(k) if k else True for k in node.keys
            ) and all(_is_pure_expression(v) for v in node.values)
        return all(_is_pure_expression(elt) for elt in node.elts)
    if isinstance(node, ast.BinOp):
        return _is_pure_expression(node.left) and _is_pure_expression(node.right)
    if isinstance(node, ast.UnaryOp):
        return _is_pure_expression(node.operand)
    if isinstance(node, ast.BoolOp):
        return all(_is_pure_expression(v) for v in node.values)
    if isinstance(node, ast.Compare):
        return _is_pure_expression(node.left) and all(
            _is_pure_expression(c) for c in node.comparators
        )
    if isinstance(node, ast.IfExp):
        return (
            _is_pure_expression(node.test)
            and _is_pure_expression(node.body)
            and _is_pure_expression(node.orelse)
        )
    # Function calls, attribute access, subscripts are NOT pure
    return False


class _UnusedVariableRemover(ast.NodeTransformer):
    """AST transformer that removes unused variable assignments."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        node.body = self._clean_body(node)
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        node.body = self._clean_body(node)
        return node

    def _clean_body(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[ast.stmt]:
        """Remove unused assignments from the function body."""
        # Compute unused set
        assignments = _collect_assignments(func_node)
        references = _collect_references(func_node)

        unused_safe = set()
        for var_name, info in assignments.items():
            if var_name.startswith("_"):
                continue
            if var_name not in references and _is_pure_expression(info["rhs"]):
                unused_safe.add(var_name)

        if not unused_safe:
            return func_node.body

        # Filter out the unused assignments
        return self._filter_stmts(func_node.body, unused_safe)

    def _filter_stmts(
        self, stmts: list[ast.stmt], unused: set[str]
    ) -> list[ast.stmt]:
        """Recursively filter unused assignments from a statement list."""
        result = []
        for stmt in stmts:
            if self._is_removable(stmt, unused):
                continue
            # Recurse into compound statements
            if isinstance(stmt, ast.If):
                stmt.body = self._filter_stmts(stmt.body, unused)
                if stmt.orelse:
                    stmt.orelse = self._filter_stmts(stmt.orelse, unused)
            elif isinstance(stmt, (ast.For, ast.While)):
                stmt.body = self._filter_stmts(stmt.body, unused)
                if stmt.orelse:
                    stmt.orelse = self._filter_stmts(stmt.orelse, unused)
            elif isinstance(stmt, ast.With):
                stmt.body = self._filter_stmts(stmt.body, unused)
            elif isinstance(stmt, ast.Try):
                stmt.body = self._filter_stmts(stmt.body, unused)
                for handler in stmt.handlers:
                    handler.body = self._filter_stmts(handler.body, unused)
                if stmt.orelse:
                    stmt.orelse = self._filter_stmts(stmt.orelse, unused)
                if stmt.finalbody:
                    stmt.finalbody = self._filter_stmts(stmt.finalbody, unused)
            result.append(stmt)

        # Ensure body is never empty
        if not result:
            result.append(ast.Pass())

        return result

    def _is_removable(self, stmt: ast.stmt, unused: set[str]) -> bool:
        """Check if a statement is a removable unused assignment."""
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                return stmt.targets[0].id in unused
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.value is not None:
                return stmt.target.id in unused
        return False
