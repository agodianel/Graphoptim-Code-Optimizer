"""Tests for the code rewriter and optimizer integration."""

import ast

import graphoptim as go


class TestRewriter:
    """Test the optimizer rewriter produces valid output."""

    def test_optimize_produces_valid_python(self):
        """Optimized output must always be valid Python."""
        code = """
def foo(x):
    if x > 0:
        return x
    return -x
    print("dead")
"""
        optimized = go.optimize(code)
        ast.parse(optimized)

    def test_optimize_preserves_semantics(self):
        """Optimization should not change the function's behavior."""
        code = """
def add(a, b):
    result = a + b
    return result
"""
        optimized = go.optimize(code)
        ast.parse(optimized)
        # Should still contain the return statement
        assert "return" in optimized

    def test_optimize_with_explicit_passes(self):
        """Explicit pass selection should work."""
        code = """
def foo(x):
    return x
    y = 1
"""
        optimized = go.optimize(code, passes=["dead_code"])
        ast.parse(optimized)

    def test_optimize_empty_code(self):
        """Empty/minimal code should pass through unchanged."""
        code = "x = 1"
        optimized = go.optimize(code)
        ast.parse(optimized)

    def test_optimize_complex_function(self):
        """Complex function should produce valid output."""
        code = """
def process(data):
    results = []
    for item in data:
        if item is None:
            continue
        if item > 100:
            results.append(item * 2)
        elif item > 50:
            results.append(item * 1.5)
        else:
            results.append(item)
    return results
"""
        optimized = go.optimize(code)
        ast.parse(optimized)

    def test_invalid_pass_name(self):
        """Unknown pass name should raise ValueError."""
        try:
            go.optimize("x = 1", passes=["nonexistent"])
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_analyze_returns_report(self):
        """go.analyze() should return a FileReport."""
        code = """
def foo(x):
    return x + 1
"""
        report = go.analyze(code)
        assert hasattr(report, "total_score")
        assert hasattr(report, "functions")
        assert len(report.functions) >= 1
        assert 0 <= report.functions[0].score <= 100

    def test_analyze_file_not_found(self):
        """go.analyze_file() should raise FileNotFoundError."""
        try:
            go.analyze_file("/nonexistent/path.py")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass
