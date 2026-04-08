"""
Control Flow Graph (CFG) builder for GraphOptim.

Builds a CFG from Python source code using the built-in `ast` module,
producing a NetworkX DiGraph. This is a custom implementation that
avoids dependency on the unmaintained `staticfg` library and works
with modern Python versions (3.9+).

Each node in the graph represents a basic block (a sequence of statements
with no branches). Edges represent control flow transitions, weighted by
estimated computational cost.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

from graphoptim.parser.ast_utils import get_operation_weight


@dataclass
class BasicBlock:
    """A basic block in the CFG — a straight-line sequence of statements."""

    id: int
    statements: list[ast.stmt] = field(default_factory=list)
    label: str = ""
    lineno: Optional[int] = None
    end_lineno: Optional[int] = None

    def add_statement(self, stmt: ast.stmt) -> None:
        """Add a statement to this block."""
        self.statements.append(stmt)
        if self.lineno is None:
            self.lineno = getattr(stmt, "lineno", None)
        self.end_lineno = getattr(stmt, "end_lineno", self.lineno)

    @property
    def is_empty(self) -> bool:
        return len(self.statements) == 0

    def compute_weight(self) -> float:
        """Compute total weight of all statements in this block."""
        return sum(get_operation_weight(stmt) for stmt in self.statements)


class CFGBuilder:
    """
    Builds a Control Flow Graph from Python source code.

    The resulting graph is a NetworkX DiGraph where:
    - Nodes are basic block IDs (integers)
    - Node attributes: 'block' (BasicBlock), 'label', 'lineno'
    - Edge attributes: 'weight' (estimated cost)
    """

    def __init__(self) -> None:
        self._block_counter: int = 0
        self._blocks: dict[int, BasicBlock] = {}

    def _new_block(self, label: str = "") -> BasicBlock:
        """Create a new basic block with a unique ID."""
        block = BasicBlock(id=self._block_counter, label=label)
        self._blocks[block.id] = block
        self._block_counter += 1
        return block

    def build(self, source_code: str, func_name: Optional[str] = None) -> nx.DiGraph:
        """
        Build a CFG from Python source code.

        If func_name is provided, only build the CFG for that function.
        Otherwise, build the CFG for the entire module.

        Args:
            source_code: Python source code string.
            func_name: Optional function name to extract CFG for.

        Returns:
            NetworkX DiGraph representing the control flow graph.
        """
        self._block_counter = 0
        self._blocks = {}

        tree = ast.parse(source_code)

        if func_name:
            # Find the specific function
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        return self._build_from_function(node)
            raise ValueError(f"Function '{func_name}' not found in source code")
        else:
            # Build CFG for the entire module body
            return self._build_from_body(tree.body, "module")

    def _build_from_function(self, func_node: ast.FunctionDef) -> nx.DiGraph:
        """Build CFG from a function definition."""
        return self._build_from_body(func_node.body, func_node.name)

    def _build_from_body(
        self, body: list[ast.stmt], name: str
    ) -> nx.DiGraph:
        """
        Build CFG from a list of statements.

        Algorithm:
        1. Create entry and exit blocks.
        2. Walk through statements sequentially.
        3. For branching statements (if/for/while/try), create sub-graphs
           and connect them properly.
        4. Return the complete DiGraph.
        """
        G = nx.DiGraph()

        entry_block = self._new_block(f"{name}_entry")
        exit_block = self._new_block(f"{name}_exit")

        # Process the body and get the set of blocks that flow into the exit
        after_blocks = self._process_stmts(G, body, entry_block, exit_block)

        # Connect all "after" blocks to the exit
        for blk in after_blocks:
            if blk.id != exit_block.id:
                G.add_edge(blk.id, exit_block.id, weight=0.1)

        # Add all blocks as nodes with their attributes
        for block in self._blocks.values():
            if block.id in G.nodes or block.id == entry_block.id or block.id == exit_block.id:
                G.add_node(
                    block.id,
                    block=block,
                    label=block.label,
                    lineno=block.lineno,
                )

        # Ensure entry and exit are always in the graph
        G.add_node(
            entry_block.id,
            block=entry_block,
            label=entry_block.label,
            lineno=entry_block.lineno,
        )
        G.add_node(
            exit_block.id,
            block=exit_block,
            label=exit_block.label,
            lineno=exit_block.lineno,
        )

        return G

    def _process_stmts(
        self,
        G: nx.DiGraph,
        stmts: list[ast.stmt],
        current_block: BasicBlock,
        exit_block: BasicBlock,
    ) -> list[BasicBlock]:
        """
        Process a sequence of statements, building the CFG edges.

        Returns the list of blocks that represent the "end" of execution
        for this statement sequence (i.e., blocks that should connect to
        whatever comes next).
        """
        active_blocks = [current_block]

        for stmt in stmts:
            if not active_blocks:
                # Dead code — nothing flows here, but we still track it
                dead_block = self._new_block("dead")
                dead_block.add_statement(stmt)
                G.add_node(dead_block.id, block=dead_block, label="dead", lineno=dead_block.lineno)
                continue

            # For branching statements, we need special handling
            if isinstance(stmt, ast.If):
                active_blocks = self._process_if(G, stmt, active_blocks, exit_block)
            elif isinstance(stmt, (ast.For, ast.While)):
                active_blocks = self._process_loop(G, stmt, active_blocks, exit_block)
            elif isinstance(stmt, ast.Try):
                active_blocks = self._process_try(G, stmt, active_blocks, exit_block)
            elif isinstance(stmt, ast.With):
                active_blocks = self._process_with(G, stmt, active_blocks, exit_block)
            elif isinstance(stmt, (ast.Return, ast.Raise)):
                # Terminal statements — add to current blocks and flow to exit
                for blk in active_blocks:
                    blk.add_statement(stmt)
                    weight = get_operation_weight(stmt)
                    G.add_edge(blk.id, exit_block.id, weight=weight)
                active_blocks = []  # Nothing flows after return/raise
            elif isinstance(stmt, (ast.Break, ast.Continue)):
                # These are handled by the loop processor
                for blk in active_blocks:
                    blk.add_statement(stmt)
                active_blocks = []  # Flow handled by loop context
            else:
                # Simple statement — add to all active blocks
                for blk in active_blocks:
                    blk.add_statement(stmt)

        return active_blocks

    def _process_if(
        self,
        G: nx.DiGraph,
        if_node: ast.If,
        predecessors: list[BasicBlock],
        exit_block: BasicBlock,
    ) -> list[BasicBlock]:
        """Process an if/elif/else statement."""
        result_blocks = []

        # Condition block — add the test to predecessors
        cond_block = self._new_block("if_cond")
        for pred in predecessors:
            weight = get_operation_weight(if_node)
            G.add_edge(pred.id, cond_block.id, weight=weight)

        # True branch
        true_block = self._new_block("if_true")
        G.add_edge(cond_block.id, true_block.id, weight=0.5)
        true_after = self._process_stmts(G, if_node.body, true_block, exit_block)
        result_blocks.extend(true_after)

        # False branch (else/elif)
        if if_node.orelse:
            false_block = self._new_block("if_false")
            G.add_edge(cond_block.id, false_block.id, weight=0.5)
            false_after = self._process_stmts(G, if_node.orelse, false_block, exit_block)
            result_blocks.extend(false_after)
        else:
            # No else — the condition block itself flows through
            result_blocks.append(cond_block)

        return result_blocks

    def _process_loop(
        self,
        G: nx.DiGraph,
        loop_node: ast.For | ast.While,
        predecessors: list[BasicBlock],
        exit_block: BasicBlock,
    ) -> list[BasicBlock]:
        """Process a for/while loop."""
        result_blocks = []

        # Loop header (condition check)
        header_block = self._new_block("loop_header")
        for pred in predecessors:
            weight = get_operation_weight(loop_node)
            G.add_edge(pred.id, header_block.id, weight=weight)

        # Loop body
        body_block = self._new_block("loop_body")
        G.add_edge(header_block.id, body_block.id, weight=1.0)  # Enter loop

        body_after = self._process_stmts(G, loop_node.body, body_block, exit_block)

        # Back edge — loop body flows back to header
        for blk in body_after:
            G.add_edge(blk.id, header_block.id, weight=0.5)

        # Loop exit — header flows to after-loop
        after_loop = self._new_block("loop_exit")
        G.add_edge(header_block.id, after_loop.id, weight=0.5)  # Skip/exit loop

        # Handle else clause on loop
        if loop_node.orelse:
            else_block = self._new_block("loop_else")
            G.add_edge(header_block.id, else_block.id, weight=0.3)
            else_after = self._process_stmts(G, loop_node.orelse, else_block, exit_block)
            result_blocks.extend(else_after)

        result_blocks.append(after_loop)
        return result_blocks

    def _process_try(
        self,
        G: nx.DiGraph,
        try_node: ast.Try,
        predecessors: list[BasicBlock],
        exit_block: BasicBlock,
    ) -> list[BasicBlock]:
        """Process a try/except/else/finally statement."""
        result_blocks = []

        # Try body
        try_block = self._new_block("try_body")
        for pred in predecessors:
            weight = get_operation_weight(try_node)
            G.add_edge(pred.id, try_block.id, weight=weight)

        try_after = self._process_stmts(G, try_node.body, try_block, exit_block)

        # Exception handlers
        for handler in try_node.handlers:
            handler_block = self._new_block(
                f"except_{handler.type.id if handler.type and isinstance(handler.type, ast.Name) else 'bare'}"
            )
            G.add_edge(try_block.id, handler_block.id, weight=2.0)

            handler_after = self._process_stmts(G, handler.body, handler_block, exit_block)
            result_blocks.extend(handler_after)

        # Else clause (runs if no exception)
        if try_node.orelse:
            else_block = self._new_block("try_else")
            for blk in try_after:
                G.add_edge(blk.id, else_block.id, weight=0.5)
            else_after = self._process_stmts(G, try_node.orelse, else_block, exit_block)
            result_blocks.extend(else_after)
        else:
            result_blocks.extend(try_after)

        # Finally clause
        if try_node.finalbody:
            finally_block = self._new_block("finally")
            for blk in result_blocks:
                G.add_edge(blk.id, finally_block.id, weight=1.0)

            finally_after = self._process_stmts(G, try_node.finalbody, finally_block, exit_block)
            return finally_after

        return result_blocks

    def _process_with(
        self,
        G: nx.DiGraph,
        with_node: ast.With,
        predecessors: list[BasicBlock],
        exit_block: BasicBlock,
    ) -> list[BasicBlock]:
        """Process a with statement."""
        with_block = self._new_block("with")
        for pred in predecessors:
            G.add_edge(pred.id, with_block.id, weight=2.0)

        return self._process_stmts(G, with_node.body, with_block, exit_block)


def build_cfg(source_code: str, func_name: Optional[str] = None) -> nx.DiGraph:
    """
    Convenience function to build a CFG from source code.

    Args:
        source_code: Python source code string.
        func_name: Optional function name to build CFG for.

    Returns:
        NetworkX DiGraph representing the control flow graph.
    """
    builder = CFGBuilder()
    return builder.build(source_code, func_name)
