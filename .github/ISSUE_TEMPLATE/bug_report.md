---
name: Bug Report
about: Report a bug in GraphOptim
title: "[BUG] "
labels: bug
assignees: ''
---

## Description

A clear and concise description of the bug.

## Steps to Reproduce

1. Install GraphOptim: `pip install graphoptim`
2. Run the following code:

```python
import graphoptim as go

code = """
# paste the code that triggers the bug
"""

result = go.analyze(code)  # or go.optimize(code)
```

3. See error

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened. Include the full error traceback if applicable.

## Environment

- **GraphOptim version**: `0.1.0`
- **Python version**: `3.x.x`
- **OS**: Linux / macOS / Windows
- **Installed via**: pip / uv / source

## Additional Context

- Does the input code parse correctly with `ast.parse()`?
- Does the bug occur with `--verbose` flag?
- Any relevant `graphoptim analyze` output?

## Input Code (if applicable)

```python
# Minimal reproducible code sample that triggers the bug
```
