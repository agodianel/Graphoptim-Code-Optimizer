# Installation

## Quick Install (PyPI)

```bash
pip install graphoptim
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install graphoptim
```

## Install with Benchmark Dependencies

To use the benchmark pipeline (requires API keys):

```bash
pip install "graphoptim[benchmark]"
```

## Install from Source

```bash
git clone https://github.com/YOUR-ORG/graphoptim.git
cd graphoptim

# Using uv (recommended)
uv pip install -e ".[dev,benchmark]"

# Or using pip
pip install -e ".[dev,benchmark]"
```

## Verify Installation

```bash
graphoptim --version
# graphoptim, version 0.1.0

graphoptim config show
```

## Requirements

- **Python** ≥ 3.9
- **Core dependencies** (installed automatically):
  - `networkx` ≥ 3.0 — Graph algorithms
  - `radon` ≥ 6.0 — Cyclomatic complexity
  - `scipy` ≥ 1.10 — Statistical tests
  - `pandas` ≥ 2.0 — Data analysis
  - `rich` ≥ 13.0 — CLI output
  - `click` ≥ 8.0 — CLI framework

## Environment Variables

For the benchmark pipeline, set these environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # Claude Opus 4.6
export OPENAI_API_KEY="sk-..."           # GPT-5.2
export GOOGLE_API_KEY="AI..."            # Gemini 2.5 Pro
```
