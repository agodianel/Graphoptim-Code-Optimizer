# Contributing to GraphOptim

Thank you for your interest in contributing to GraphOptim! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Adding Optimization Passes](#adding-optimization-passes)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior via the repository issues.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create a branch** for your contribution
4. **Make your changes** following the guidelines below
5. **Submit a Pull Request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/graphoptim.git
cd graphoptim

# Install with uv (recommended)
uv pip install -e ".[dev,benchmark]"

# Verify setup
uv run pytest tests/ -v
uv run graphoptim --version
```

### Required Tools

- **Python** ≥ 3.9
- **uv** (recommended) or pip
- **Git**

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feat/dead-code-pass-improvements` — New features
- `fix/cfg-builder-async-functions` — Bug fixes
- `docs/update-benchmark-section` — Documentation
- `refactor/metrics-extraction` — Code refactoring
- `test/add-centrality-pass-tests` — Test additions

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add critical path optimizer pass
fix: handle async functions in CFG builder
docs: update benchmark results in README
test: add regression tests for path shortener
refactor: extract metric computation into helper
```

## Pull Request Process

1. **Update tests** — All new code must have corresponding tests
2. **Run the full test suite** — `uv run pytest tests/ -v`
3. **Run linting** — `uv run ruff check .`
4. **Run formatting** — `uv run black .`
5. **Update CHANGELOG.md** — Add your changes under `[Unreleased]`
6. **Fill out the PR template** — Describe what and why

### PR Requirements

- [ ] All tests pass
- [ ] Code is formatted (black) and linted (ruff)
- [ ] New code has docstrings
- [ ] CHANGELOG.md is updated
- [ ] No breaking changes without discussion

## Coding Standards

### Style

- **Formatter**: `black` with default settings
- **Linter**: `ruff` with rules E, F, I, W
- **Type hints**: Required for all public API functions
- **Docstrings**: Google-style docstrings for all public classes and functions

### Example

```python
def detect_dead_nodes(cfg: nx.DiGraph) -> list[DeadNode]:
    """
    Detect dead (unreachable) code blocks in a CFG.

    A dead node is one with in-degree=0 that is not the entry node.

    Args:
        cfg: NetworkX DiGraph representing the CFG.

    Returns:
        List of DeadNode objects.
    """
    ...
```

### Design Constraints

- **Never break working code** — The optimizer must produce syntactically valid, semantically equivalent code
- **Preserve docstrings and comments** — AST rewrites must carry through all decorators, docstrings, and inline comments
- **Dry-run by default** — `optimize()` returns a string; never writes to disk unless explicitly asked
- **Graceful degradation** — If a pass fails, skip it rather than crashing

## Adding Optimization Passes

GraphOptim is designed to be extensible. To add a new optimization pass:

### 1. Create the pass module

Create a new file in `graphoptim/optimizer/passes/`:

```python
# graphoptim/optimizer/passes/my_pass.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class MyPassFinding:
    """A finding from this pass."""
    line: Optional[int]
    description: str

class MyPass:
    """Description of what this pass does."""

    name = "my_pass"
    cost = 0.3   # Risk level (0.0-1.0)
    benefit = 0.0  # Set dynamically during detection

    def detect(self, source_code: str, func_name=None) -> list[MyPassFinding]:
        """Detect issues."""
        ...

    def fix(self, source_code: str) -> str:
        """Apply fixes. Must return valid Python."""
        ...
```

### 2. Register in the rewriter

Add your pass to `PASS_REGISTRY` in `graphoptim/optimizer/rewriter.py`.

### 3. Add tests

Create `tests/test_my_pass.py` with both detection and fix tests.

### 4. Update documentation

- Add the pass to the table in `README.md`
- Add an entry to `CHANGELOG.md`

## Questions?

Open an issue or start a discussion. We're happy to help!
