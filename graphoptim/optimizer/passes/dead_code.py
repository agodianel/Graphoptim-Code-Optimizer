"""
Dead Code Elimination pass for GraphOptim.

Detects and removes unreachable code blocks from Python source code.
This includes code after return/raise/break/continue statements
and unreachable branches in the CFG.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import Optional

import networkx as nx

from graphoptim.analyzer.patterns import DeadNode, detect_dead_nodes
from graphoptim.parser.cfg_builder import build_cfg


@dataclass
class DeadCodeFinding:
    """A specific dead code finding with fix information."""

    line: Optional[int]
    end_line: Optional[int]
    description: str
    node: Optional[ast.AST] = None


class DeadCodePass:
    """
    Dead code elimination optimization pass.

    Detection: Nodes in the CFG with in_degree == 0 that are not the
    function entry point, plus statements after terminal statements
    (return, raise, break, continue).

    Fix: Remove the corresponding AST nodes from the source.
    """

    name = "dead_code"
    cost = 0.2  # Low risk — removing dead code is safe
    benefit = 0.0  # Set dynamically based on detection

    def detect(self, source_code: str, func_name: Optional[str] = None) -> list[DeadCodeFinding]:
        """
        Find all dead code blocks in the source.

        Uses both CFG-based detection (unreachable blocks) and
        AST-based detection (code after terminal statements).

        Args:
            source_code: Python source code string.
            func_name: Optional function name to analyze.

        Returns:
            List of DeadCodeFinding objects.
        """
        findings = []

        # AST-based detection — more precise for line-level dead code
        try:
            tree = ast.parse(source_code)
            findings.extend(self._detect_after_terminal(tree))
        except SyntaxError:
            pass

        # CFG-based detection
        try:
            cfg = build_cfg(source_code, func_name)
            dead_nodes = detect_dead_nodes(cfg)
            for dn in dead_nodes:
                findings.append(
                    DeadCodeFinding(
                        line=dn.line,
                        end_line=None,
                        description=dn.description,
                    )
                )
        except Exception:
            pass

        # Deduplicate by line number
        seen_lines: set[Optional[int]] = set()
        unique = []
        for finding in findings:
            if finding.line not in seen_lines:
                seen_lines.add(finding.line)
                unique.append(finding)

        # Update benefit based on findings count
        if unique:
            self.benefit = min(len(unique) * 0.15, 0.8)

        return unique

    def fix(self, source_code: str) -> str:
        """
        Remove dead code from the source.

        Args:
            source_code: Python source code string.

        Returns:
            Source code with dead code removed.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return source_code

        # Apply the dead code removal transformer
        transformer = _DeadCodeRemover()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        try:
            return ast.unparse(new_tree)
        except Exception:
            return source_code

    def _detect_after_terminal(self, tree: ast.Module) -> list[DeadCodeFinding]:
        """Detect statements that come after return/raise/break/continue."""
        findings = []
        detector = _AfterTerminalDetector()
        detector.visit(tree)
        findings.extend(detector.findings)
        return findings


class _AfterTerminalDetector(ast.NodeVisitor):
    """AST visitor that detects code after terminal statements."""

    def __init__(self) -> None:
        self.findings: list[DeadCodeFinding] = []

    def _check_body(self, body: list[ast.stmt]) -> None:
        """Check a body for statements after terminal statements."""
        for i, stmt in enumerate(body):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                # Everything after this in the same body is dead
                for dead_stmt in body[i + 1:]:
                    self.findings.append(
                        DeadCodeFinding(
                            line=getattr(dead_stmt, "lineno", None),
                            end_line=getattr(dead_stmt, "end_lineno", None),
                            description=(
                                f"Statement at line {getattr(dead_stmt, 'lineno', '?')} "
                                f"is unreachable after "
                                f"{type(stmt).__name__.lower()} at line "
                                f"{getattr(stmt, 'lineno', '?')}"
                            ),
                            node=dead_stmt,
                        )
                    )
                break  # No need to check further

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_body(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_body(node.body)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self._check_body(node.body)
        self._check_body(node.orelse)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._check_body(node.body)
        self._check_body(node.orelse)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._check_body(node.body)
        self._check_body(node.orelse)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._check_body(node.body)
        for handler in node.handlers:
            self._check_body(handler.body)
        self._check_body(node.orelse)
        self._check_body(node.finalbody)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self._check_body(node.body)
        self.generic_visit(node)


class _DeadCodeRemover(ast.NodeTransformer):
    """AST transformer that removes dead code after terminal statements."""

    def _clean_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
        """Remove statements after terminal statements in a body."""
        cleaned = []
        for stmt in body:
            # First, recursively clean the statement
            stmt = self.visit(stmt)
            if stmt is not None:
                cleaned.append(stmt)
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    break  # Stop — everything after is dead

        # Ensure body is not empty (Python requires at least one statement)
        if not cleaned:
            cleaned.append(ast.Pass())

        return cleaned

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.body = self._clean_body(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        node.body = self._clean_body(node.body)
        return node

    def visit_If(self, node: ast.If) -> ast.If:
        node.body = self._clean_body(node.body)
        if node.orelse:
            node.orelse = self._clean_body(node.orelse)
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        node.body = self._clean_body(node.body)
        if node.orelse:
            node.orelse = self._clean_body(node.orelse)
        return node

    def visit_While(self, node: ast.While) -> ast.While:
        node.body = self._clean_body(node.body)
        if node.orelse:
            node.orelse = self._clean_body(node.orelse)
        return node

    def visit_Try(self, node: ast.Try) -> ast.Try:
        node.body = self._clean_body(node.body)
        for handler in node.handlers:
            handler.body = self._clean_body(handler.body)
        if node.orelse:
            node.orelse = self._clean_body(node.orelse)
        if node.finalbody:
            node.finalbody = self._clean_body(node.finalbody)
        return node

    def visit_With(self, node: ast.With) -> ast.With:
        node.body = self._clean_body(node.body)
        return node
