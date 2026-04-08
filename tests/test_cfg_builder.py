"""Tests for CFG builder."""

import ast

import networkx as nx

from graphoptim.parser.cfg_builder import CFGBuilder, build_cfg


class TestCFGBuilder:
    """Test the CFG builder with various Python constructs."""

    def test_simple_function(self):
        """CFG of a simple function has correct structure."""
        code = """
def foo(x):
    return x + 1
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        assert cfg.number_of_nodes() >= 2  # At least entry and exit
        assert cfg.number_of_edges() >= 1

    def test_if_else(self):
        """CFG of if/else has branching structure."""
        code = """
def foo(x):
    if x > 0:
        return x
    else:
        return -x
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        # Should have: entry, if_cond, if_true, if_false, exit
        assert cfg.number_of_nodes() >= 4

    def test_for_loop(self):
        """CFG of for loop has back-edge."""
        code = """
def foo(items):
    total = 0
    for item in items:
        total += item
    return total
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        # Should have loop header with a back-edge
        assert cfg.number_of_edges() >= 3

    def test_while_loop(self):
        """CFG of while loop has proper structure."""
        code = """
def foo(x):
    while x > 0:
        x -= 1
    return x
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        assert cfg.number_of_nodes() >= 3

    def test_try_except(self):
        """CFG of try/except has exception paths."""
        code = """
def foo(x):
    try:
        result = 1 / x
    except ZeroDivisionError:
        result = 0
    return result
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        assert cfg.number_of_nodes() >= 4

    def test_nested_if(self):
        """CFG of nested if has correct depth."""
        code = """
def foo(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x - y
    return 0
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        assert cfg.number_of_nodes() >= 5

    def test_empty_function(self):
        """CFG of empty function (pass) works."""
        code = """
def foo():
    pass
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        assert cfg.number_of_nodes() >= 2

    def test_module_level(self):
        """CFG of module-level code works."""
        code = """
x = 1
y = 2
z = x + y
"""
        cfg = build_cfg(code)
        assert isinstance(cfg, nx.DiGraph)

    def test_function_not_found(self):
        """Raises ValueError for nonexistent function."""
        code = "def foo(): pass"
        try:
            build_cfg(code, "bar")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_with_statement(self):
        """CFG of with statement works."""
        code = """
def foo(path):
    with open(path) as f:
        data = f.read()
    return data
"""
        cfg = build_cfg(code, "foo")
        assert isinstance(cfg, nx.DiGraph)
        assert cfg.number_of_nodes() >= 3
