"""Tests for unused variable elimination pass."""

import ast

from graphoptim.optimizer.passes.unused_variable import UnusedVariablePass


class TestUnusedVariableDetection:
    """Test unused variable detection."""

    def test_detect_simple_unused(self):
        """Simple unused variable should be detected."""
        code = """
def foo(x):
    temp = x + 1
    return x * 2
"""
        pass_ = UnusedVariablePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1
        assert any(f.variable_name == "temp" for f in findings)

    def test_detect_used_variable(self):
        """Used variables should NOT be flagged."""
        code = """
def foo(x):
    result = x + 1
    return result
"""
        pass_ = UnusedVariablePass()
        findings = pass_.detect(code)
        used_names = [f.variable_name for f in findings]
        assert "result" not in used_names

    def test_detect_underscore_convention(self):
        """Underscore-prefixed vars should be ignored (convention)."""
        code = """
def foo(x):
    _unused = x + 1
    return x * 2
"""
        pass_ = UnusedVariablePass()
        findings = pass_.detect(code)
        names = [f.variable_name for f in findings]
        assert "_unused" not in names

    def test_detect_function_arg_not_flagged(self):
        """Function arguments should NOT be flagged as unused assignments."""
        code = """
def foo(x, y):
    return x
"""
        pass_ = UnusedVariablePass()
        findings = pass_.detect(code)
        names = [f.variable_name for f in findings]
        assert "x" not in names
        assert "y" not in names

    def test_detect_side_effect_rhs(self):
        """Assignments with side-effect RHS should be flagged but marked unsafe."""
        code = """
def foo(items):
    result = process(items)
    return items
"""
        pass_ = UnusedVariablePass()
        findings = pass_.detect(code)
        assert len(findings) >= 1
        # Should be marked as NOT safe to remove (function call)
        result_finding = [f for f in findings if f.variable_name == "result"]
        if result_finding:
            assert not result_finding[0].is_safe_to_remove

    def test_detect_multiple_unused(self):
        """Multiple unused variables should all be detected."""
        code = """
def foo(x):
    a = 1
    b = 2
    c = 3
    return x
"""
        pass_ = UnusedVariablePass()
        findings = pass_.detect(code)
        assert len(findings) >= 3


class TestUnusedVariableElimination:
    """Test unused variable removal."""

    def test_fix_removes_unused(self):
        """Unused pure assignments should be removed."""
        code = """
def foo(x):
    temp = x + 1
    debug = "test"
    return x * 2
"""
        pass_ = UnusedVariablePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "temp" not in optimized
        assert "debug" not in optimized
        assert "return" in optimized

    def test_fix_preserves_used(self):
        """Used variables should not be removed."""
        code = """
def foo(x):
    result = x * 2
    return result
"""
        pass_ = UnusedVariablePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        assert "result" in optimized

    def test_fix_preserves_side_effects(self):
        """Assignments with side-effect RHS should NOT be removed."""
        code = """
def foo(items):
    result = process(items)
    return items
"""
        pass_ = UnusedVariablePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)
        # process() call should still be present (side effect)
        assert "process" in optimized

    def test_fix_produces_valid_python(self):
        """Output must always be valid Python."""
        code = """
def foo(x):
    a = 1
    b = 2
    return x
"""
        pass_ = UnusedVariablePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)

    def test_fix_doesnt_empty_body(self):
        """Removing all assignments should leave at least a pass."""
        code = """
def foo():
    a = 1
    b = 2
"""
        pass_ = UnusedVariablePass()
        optimized = pass_.fix(code)
        ast.parse(optimized)  # Must not raise
