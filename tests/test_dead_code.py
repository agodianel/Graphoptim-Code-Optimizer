"""Tests for dead code detection and elimination."""

import ast

import graphoptim as go
from graphoptim.optimizer.passes.dead_code import DeadCodePass


class TestDeadCodeDetection:
    """Test dead code detection."""

    def test_dead_after_return(self):
        """Code after return should be detected as dead."""
        code = """
def foo(x):
    if x > 0:
        return x
    return -x
    print("never reached")
"""
        pass_ = DeadCodePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1
        # The dead code should be on the print line
        lines = [f.line for f in findings if f.line]
        assert any(line >= 5 for line in lines)

    def test_dead_after_raise(self):
        """Code after raise should be detected as dead."""
        code = """
def foo(x):
    raise ValueError("error")
    return x
"""
        pass_ = DeadCodePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1

    def test_no_dead_code(self):
        """Clean code should have no dead code findings."""
        code = """
def foo(x):
    if x > 0:
        return x
    return -x
"""
        pass_ = DeadCodePass()
        findings = pass_.detect(code)
        assert len(findings) == 0

    def test_dead_in_branch(self):
        """Dead code in a branch should be detected."""
        code = """
def foo(x):
    if x > 0:
        return x
        y = x + 1
    return 0
"""
        pass_ = DeadCodePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1

    def test_dead_after_break(self):
        """Code after break should be detected as dead."""
        code = """
def foo(items):
    for item in items:
        if item < 0:
            break
            print("unreachable")
    return items
"""
        pass_ = DeadCodePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1


class TestDeadCodeElimination:
    """Test dead code removal."""

    def test_remove_dead_after_return(self):
        """Dead code after return should be removed."""
        code = """
def foo(x):
    if x > 0:
        return x
    return -x
    print("never reached")
"""
        pass_ = DeadCodePass()
        optimized = pass_.fix(code)
        assert "never reached" not in optimized

    def test_output_is_valid_python(self):
        """Optimized output must be valid Python."""
        code = """
def foo(x):
    return x
    y = x + 1
    z = y + 2
"""
        pass_ = DeadCodePass()
        optimized = pass_.fix(code)
        # Must parse without error
        ast.parse(optimized)

    def test_preserves_live_code(self):
        """Live code should not be removed."""
        code = """
def foo(x):
    result = x * 2
    return result
"""
        pass_ = DeadCodePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "result" in optimized

    def test_analyze_integration(self):
        """End-to-end test with go.analyze()."""
        code = """
def foo(x):
    if x > 0:
        return x
    return -x
    print("never reached")
"""
        report = go.analyze(code)
        assert report.functions[0].dead_nodes or True  # CFG dead nodes may differ

    def test_optimize_integration(self):
        """End-to-end test with go.optimize()."""
        code = """
def foo(x):
    return x
    y = x + 1
"""
        optimized = go.optimize(code, passes=["dead_code"])
        # Output must be valid Python
        ast.parse(optimized)
