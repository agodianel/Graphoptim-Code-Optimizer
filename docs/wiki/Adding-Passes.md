# Adding New Optimization Passes

GraphOptim is designed to be extensible. This guide walks you through adding a new optimization pass.

## Pass Architecture

Every pass implements two methods:

- `detect(source_code, func_name?) → list[Finding]` — Find issues
- `fix(source_code) → str` — Apply fixes (must return valid Python)

And two attributes for the knapsack selector:

- `cost: float` — Risk level (0.0 = safe, 1.0 = dangerous)
- `benefit: float` — Set dynamically during `detect()` based on findings

## Step-by-Step Guide

### 1. Create the Pass Module

```python
# graphoptim/optimizer/passes/variable_shadowing.py

"""
Variable Shadowing Detection pass for GraphOptim.

Detects inner scope variables that shadow outer scope names,
a common pattern in AI-generated code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional


@dataclass
class ShadowingFinding:
    """A variable shadowing finding."""
    inner_name: str
    inner_line: Optional[int]
    outer_line: Optional[int]
    description: str


class VariableShadowingPass:
    """
    Detects and suggests fixes for variable shadowing.

    Detection: Inner scope variable names that match outer scope names.
    Fix: Rename inner variables to avoid shadowing (advisory via comments).
    """

    name = "variable_shadowing"
    cost = 0.4   # Medium risk — renaming variables
    benefit = 0.0  # Set dynamically

    def detect(
        self, source_code: str, func_name: Optional[str] = None
    ) -> list[ShadowingFinding]:
        """Find shadowed variables."""
        findings = []
        # ... detection logic ...

        if findings:
            self.benefit = min(len(findings) * 0.1, 0.5)
        return findings

    def fix(self, source_code: str) -> str:
        """Apply fixes. Must return valid Python."""
        findings = self.detect(source_code)
        if not findings:
            return source_code

        # Apply transformation...
        # CRITICAL: validate output
        import ast
        result = source_code  # ... transform ...
        ast.parse(result)  # Must not raise
        return result
```

### 2. Register in the Rewriter

Edit `graphoptim/optimizer/rewriter.py`:

```python
from graphoptim.optimizer.passes.variable_shadowing import VariableShadowingPass

PASS_REGISTRY: dict[str, type] = {
    "dead_code": DeadCodePass,
    "path_shortener": PathShortenerPass,
    "centrality": CentralityPass,
    "variable_shadowing": VariableShadowingPass,  # ADD THIS
}
```

### 3. Write Tests

Create `tests/test_variable_shadowing.py`:

```python
"""Tests for variable shadowing detection."""

import ast
from graphoptim.optimizer.passes.variable_shadowing import VariableShadowingPass


class TestVariableShadowingDetection:
    def test_inner_shadows_outer(self):
        code = '''
def foo():
    x = 1
    def bar():
        x = 2  # Shadows outer x
        return x
    return bar()
'''
        pass_ = VariableShadowingPass()
        findings = pass_.detect(code)
        assert len(findings) >= 1

    def test_no_shadowing(self):
        code = '''
def foo():
    x = 1
    return x
'''
        pass_ = VariableShadowingPass()
        findings = pass_.detect(code)
        assert len(findings) == 0


class TestVariableShadowingFix:
    def test_output_is_valid_python(self):
        code = '''
def foo():
    x = 1
    def bar():
        x = 2
        return x
    return bar()
'''
        pass_ = VariableShadowingPass()
        result = pass_.fix(code)
        ast.parse(result)  # Must not raise

    def test_preserves_semantics(self):
        """Fix should not change observable behavior."""
        ...
```

### 4. Update Documentation

**README.md** — Add to the passes table:

```markdown
| `variable_shadowing` | Inner scope shadows outer variables | Renames or adds advisory comments |
```

**CHANGELOG.md** — Add under `[Unreleased]`:

```markdown
### Added
- Variable shadowing detection and advisory pass
```

## Design Rules

1. **Never break working code** — If unsure, skip the fix and emit a warning
2. **Validate with ast.parse()** — Every `fix()` output MUST parse
3. **Set benefit dynamically** — Based on what `detect()` actually finds
4. **Be conservative with cost** — Automated refactoring is risky
5. **Preserve comments and docstrings** — Use AST transformations carefully
6. **Handle edge cases** — Async functions, decorators, nested classes

## Knapsack Integration

Your pass automatically participates in knapsack selection. The selector will:

1. Call `detect()` to set `benefit` dynamically
2. Use `cost` and `benefit` to decide inclusion
3. Respect `prerequisites` if your pass depends on others

```python
class MyPass:
    name = "my_pass"
    cost = 0.3
    benefit = 0.0  # Updated by detect()
    prerequisites = ["dead_code"]  # Optional: must run after dead_code
```
