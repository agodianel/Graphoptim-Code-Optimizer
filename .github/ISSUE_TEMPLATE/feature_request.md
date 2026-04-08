---
name: Feature Request
about: Suggest a new feature or optimization pass
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

## Summary

A clear and concise description of the feature you'd like.

## Problem / Motivation

What problem does this feature solve? Why is it needed?

## Proposed Solution

How should this feature work? Include API examples if applicable:

```python
import graphoptim as go

# How you envision using this feature
result = go.new_feature(...)
```

## For New Optimization Passes

If proposing a new optimization pass, please describe:

- **What it detects**: What structural inefficiency does this pass identify?
- **Detection algorithm**: How does it detect the pattern in the CFG/AST?
- **Fix strategy**: How should the code be transformed?
- **Risk level** (0.0-1.0): How risky is the automated fix?
- **Example**: A before/after code example

### Example

```python
# Before (inefficient)
def foo(x):
    ...

# After (optimized)
def foo(x):
    ...
```

## Alternatives Considered

Any alternative approaches or workarounds you've considered.

## Additional Context

Any other context, references, or screenshots about the feature request.
