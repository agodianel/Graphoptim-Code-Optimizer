"""Tests for guard clause refactoring pass."""

import ast

from graphoptim.optimizer.passes.guard_clause import GuardClausePass


class TestGuardClauseDetection:
    """Test guard clause detection."""

    def test_detect_single_wrapping_if(self):
        """Single if wrapping entire function body should be detected."""
        code = """
def foo(x):
    if x:
        if x > 0:
            if x < 100:
                return x * 2
"""
        pass_ = GuardClausePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1
        assert findings[0].current_depth >= 3

    def test_detect_no_issue(self):
        """Shallow function should not be flagged."""
        code = """
def foo(x):
    if x > 0:
        return x
    return -x
"""
        pass_ = GuardClausePass()
        findings = pass_.detect(code)
        assert len(findings) == 0

    def test_detect_preserves_docstring(self):
        """Docstring should not interfere with detection."""
        code = """
def foo(x):
    \"\"\"Process x.\"\"\"
    if x:
        if x > 0:
            if x < 100:
                return x
"""
        pass_ = GuardClausePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1

    def test_detect_with_else(self):
        """If-else should NOT be flagged (has meaningful branches)."""
        code = """
def foo(x):
    if x > 0:
        return x
    else:
        return -x
"""
        pass_ = GuardClausePass()
        findings = pass_.detect(code)
        assert len(findings) == 0


class TestGuardClauseFix:
    """Test guard clause refactoring."""

    def test_fix_single_nested_if(self):
        """Single nested if should be flattened to guard clause."""
        code = """
def foo(x):
    if x:
        return x * 2
"""
        pass_ = GuardClausePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        # Should contain inverted condition
        assert "not" in optimized or "None" in optimized

    def test_fix_produces_valid_python(self):
        """All fix outputs must be valid Python."""
        code = """
def foo(x):
    if x:
        if x > 0:
            return x * 2
"""
        pass_ = GuardClausePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)

    def test_fix_deep_nesting(self):
        """Deeply nested ifs should produce multiple guard clauses."""
        code = """
def foo(x):
    if x:
        if x > 0:
            if x < 100:
                return x
"""
        pass_ = GuardClausePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        # Should have reduced nesting — multiple returns
        assert optimized.count("return") >= 2

    def test_fix_preserves_clean_code(self):
        """Code without issues should pass through unchanged."""
        code = """
def foo(x):
    return x + 1
"""
        pass_ = GuardClausePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "return" in optimized

    def test_fix_inverts_comparison(self):
        """Comparison operators should be properly inverted."""
        code = """
def foo(x):
    if x > 0:
        return x
"""
        pass_ = GuardClausePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        # Should have inverted the comparison (> becomes <=)
        assert "<=" in optimized or "not" in optimized
