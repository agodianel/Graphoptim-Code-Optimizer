"""
Data Flow Graph (DFG) builder for GraphOptim.

Builds a data flow graph from Python source code, tracking variable
definitions and usages. The DFG complements the CFG by capturing
data dependencies between operations.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

from graphoptim.parser.ast_utils import parse_source


@dataclass
class VarDef:
    """A variable definition (write)."""

    name: str
    lineno: int
    node: ast.AST
    scope: str = "local"


@dataclass
class VarUse:
    """A variable usage (read)."""

    name: str
    lineno: int
    node: ast.AST


class DFGBuilder:
    """
    Builds a Data Flow Graph from Python source code.

    Nodes represent variable definitions and uses.
    Edges represent def → use relationships (data flows from
    where a variable is defined to where it is used).
    """

    def __init__(self) -> None:
        self._node_counter: int = 0
        self._definitions: dict[str, list[int]] = {}  # var_name → [node_ids]
        self._graph: nx.DiGraph = nx.DiGraph()

    def _new_node_id(self) -> int:
        """Get a new unique node ID."""
        nid = self._node_counter
        self._node_counter += 1
        return nid

    def build(self, source_code: str, func_name: Optional[str] = None) -> nx.DiGraph:
        """
        Build a DFG from Python source code.

        Args:
            source_code: Python source code string.
            func_name: Optional function name to analyze.

        Returns:
            NetworkX DiGraph representing data flow.
        """
        self._node_counter = 0
        self._definitions = {}
        self._graph = nx.DiGraph()

        tree = parse_source(source_code)

        if func_name:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        self._process_function(node)
                        return self._graph
            raise ValueError(f"Function '{func_name}' not found")
        else:
            self._process_body(tree.body)

        return self._graph

    def _process_function(self, func_node: ast.FunctionDef) -> None:
        """Process a function definition, including its arguments."""
        # Function arguments are definitions
        for arg in func_node.args.args:
            self._add_definition(arg.arg, getattr(arg, "lineno", func_node.lineno), arg)

        self._process_body(func_node.body)

    def _process_body(self, body: list[ast.stmt]) -> None:
        """Process a list of statements."""
        for stmt in body:
            self._process_stmt(stmt)

    def _process_stmt(self, stmt: ast.stmt) -> None:
        """Process a single statement, extracting defs and uses."""
        if isinstance(stmt, ast.Assign):
            # Process the value (uses) first
            for use in self._extract_uses(stmt.value):
                self._add_use(use)

            # Then process targets (definitions)
            for target in stmt.targets:
                for name_node in self._extract_names(target):
                    self._add_definition(
                        name_node.id,
                        getattr(stmt, "lineno", 0),
                        stmt,
                    )

        elif isinstance(stmt, ast.AugAssign):
            # x += expr — x is both used and defined
            for use in self._extract_uses(stmt.value):
                self._add_use(use)
            if isinstance(stmt.target, ast.Name):
                self._add_use(VarUse(stmt.target.id, stmt.lineno, stmt.target))
                self._add_definition(stmt.target.id, stmt.lineno, stmt)

        elif isinstance(stmt, ast.Return):
            if stmt.value:
                for use in self._extract_uses(stmt.value):
                    self._add_use(use)

        elif isinstance(stmt, ast.If):
            for use in self._extract_uses(stmt.test):
                self._add_use(use)
            self._process_body(stmt.body)
            self._process_body(stmt.orelse)

        elif isinstance(stmt, ast.For):
            # Loop variable is a definition
            for name_node in self._extract_names(stmt.target):
                self._add_definition(name_node.id, stmt.lineno, stmt)
            for use in self._extract_uses(stmt.iter):
                self._add_use(use)
            self._process_body(stmt.body)
            self._process_body(stmt.orelse)

        elif isinstance(stmt, ast.While):
            for use in self._extract_uses(stmt.test):
                self._add_use(use)
            self._process_body(stmt.body)
            self._process_body(stmt.orelse)

        elif isinstance(stmt, ast.Try):
            self._process_body(stmt.body)
            for handler in stmt.handlers:
                if handler.name:
                    self._add_definition(handler.name, handler.lineno, handler)
                self._process_body(handler.body)
            self._process_body(stmt.orelse)
            self._process_body(stmt.finalbody)

        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                for use in self._extract_uses(item.context_expr):
                    self._add_use(use)
                if item.optional_vars:
                    for name_node in self._extract_names(item.optional_vars):
                        self._add_definition(name_node.id, stmt.lineno, stmt)
            self._process_body(stmt.body)

        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._add_definition(stmt.name, stmt.lineno, stmt)

        elif isinstance(stmt, ast.Expr):
            for use in self._extract_uses(stmt.value):
                self._add_use(use)

    def _extract_uses(self, node: ast.expr) -> list[VarUse]:
        """Extract all variable uses from an expression."""
        uses = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                uses.append(VarUse(child.id, getattr(child, "lineno", 0), child))
        return uses

    def _extract_names(self, target: ast.AST) -> list[ast.Name]:
        """Extract Name nodes from an assignment target (handles tuples, etc.)."""
        if isinstance(target, ast.Name):
            return [target]
        elif isinstance(target, (ast.Tuple, ast.List)):
            names = []
            for elt in target.elts:
                names.extend(self._extract_names(elt))
            return names
        return []

    def _add_definition(self, name: str, lineno: int, node: ast.AST) -> None:
        """Add a variable definition node to the graph."""
        nid = self._new_node_id()
        self._graph.add_node(
            nid,
            type="def",
            var_name=name,
            lineno=lineno,
        )
        if name not in self._definitions:
            self._definitions[name] = []
        self._definitions[name].append(nid)

    def _add_use(self, use: VarUse) -> None:
        """Add a variable use node and connect it to its definition."""
        use_id = self._new_node_id()
        self._graph.add_node(
            use_id,
            type="use",
            var_name=use.name,
            lineno=use.lineno,
        )

        # Connect to the most recent definition
        if use.name in self._definitions and self._definitions[use.name]:
            def_id = self._definitions[use.name][-1]
            self._graph.add_edge(def_id, use_id, var_name=use.name)


def build_dfg(source_code: str, func_name: Optional[str] = None) -> nx.DiGraph:
    """
    Convenience function to build a DFG from source code.

    Args:
        source_code: Python source code string.
        func_name: Optional function name to build DFG for.

    Returns:
        NetworkX DiGraph representing the data flow graph.
    """
    builder = DFGBuilder()
    return builder.build(source_code, func_name)
