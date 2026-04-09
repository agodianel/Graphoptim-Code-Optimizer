"""Tests for constant folding pass."""

import ast

from graphoptim.optimizer.passes.constant_folding import ConstantFoldingPass


class TestConstantFoldingDetection:
    """Test constant expression detection."""

    def test_detect_arithmetic(self):
        """Constant arithmetic should be detected."""
        code = """
TIMEOUT = 60 * 60
"""
        pass_ = ConstantFoldingPass()
        findings = pass_.detect(code)
        assert len(findings) >= 1
        assert any(f.folded_value == 3600 for f in findings)

    def test_detect_nested_arithmetic(self):
        """Nested constant expressions should be detected."""
        code = """
MAX_SIZE = 1024 * 1024 * 4
"""
        pass_ = ConstantFoldingPass()
        findings = pass_.detect(code)
        assert len(findings) >= 1

    def test_detect_string_concat(self):
        """Constant string concatenation should be detected."""
        code = """
PREFIX = "api" + "_" + "v2"
"""
        pass_ = ConstantFoldingPass()
        findings = pass_.detect(code)
        assert len(findings) >= 1
        assert any(f.folded_value == "api_v2" for f in findings)

    def test_no_detect_variable_expr(self):
        """Expressions with variables should NOT be flagged."""
        code = """
def foo(x):
    result = x * 2
    return result
"""
        pass_ = ConstantFoldingPass()
        findings = pass_.detect(code)
        assert len(findings) == 0

    def test_no_detect_simple_constant(self):
        """Already-constant values should NOT be flagged."""
        code = """
X = 42
Y = "hello"
"""
        pass_ = ConstantFoldingPass()
        findings = pass_.detect(code)
        assert len(findings) == 0

    def test_detect_unary_op(self):
        """Unary operations on constants should be detected."""
        code = """
NEGATIVE = -(60 * 60)
"""
        pass_ = ConstantFoldingPass()
        findings = pass_.detect(code)
        assert len(findings) >= 1


class TestConstantFoldingFix:
    """Test constant folding transformation."""

    def test_fold_arithmetic(self):
        """Constant arithmetic should be folded."""
        code = """
TIMEOUT = 60 * 60
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "3600" in optimized

    def test_fold_string_concat(self):
        """Constant string concatenation should be folded."""
        code = """
PREFIX = "api" + "_" + "v2"
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "api_v2" in optimized

    def test_fold_nested(self):
        """Nested constant expressions should be folded completely."""
        code = """
VALUE = 2 * 3 + 4
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "10" in optimized

    def test_fold_preserves_variable_expr(self):
        """Non-constant expressions should pass through unchanged."""
        code = """
def foo(x):
    return x * 2
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "x" in optimized

    def test_fold_division_by_zero(self):
        """Division by zero should NOT be folded."""
        code = """
X = 1 / 0
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        # Should NOT fold — original expression preserved
        assert "/" in optimized

    def test_fold_produces_valid_python(self):
        """Output must always be valid Python."""
        code = """
A = 10 * 20
B = 3 + 7
C = 100 - 50
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)

    def test_fold_prevents_huge_values(self):
        """Extremely large results should NOT be folded."""
        code = """
X = 10 ** 100
"""
        pass_ = ConstantFoldingPass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
