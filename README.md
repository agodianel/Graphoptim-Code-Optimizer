<p align="center">
  <h1 align="center">GraphOptim</h1>
  <p align="center">
    <strong>Graph-theoretic optimizer for AI-generated Python code</strong>
  </p>
  <p align="center">
    Detects and fixes structural inefficiencies that rule-based linters cannot catch.
  </p>
</p>

<p align="center">
  <a href="https://github.com/YOUR-ORG/graphoptim/actions/workflows/ci.yml"><img src="https://github.com/YOUR-ORG/graphoptim/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/graphoptim/"><img src="https://img.shields.io/pypi/v/graphoptim.svg?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/graphoptim/"><img src="https://img.shields.io/pypi/pyversions/graphoptim.svg" alt="Python versions"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://github.com/YOUR-ORG/graphoptim/blob/main/CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg" alt="Code of Conduct"></a>
  <a href="https://github.com/YOUR-ORG/graphoptim/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-Keep%20a%20Changelog-orange.svg" alt="Changelog"></a>
</p>

---

## Why GraphOptim?

AI coding assistants (Copilot, Claude, Cursor, Gemini) produce code that *works* — but often contains **graph-level structural inefficiencies** that traditional linters miss:

- 🔴 **Redundant execution paths** — duplicate conditional branches
- 💀 **Dead code blocks** — unreachable code after returns/raises
- 🎯 **Over-centralized functions** — bottleneck nodes everything flows through
- 📏 **Inflated complexity** — unnecessarily deep execution chains

### How is this different from existing tools?

| Tool | Approach | Misses |
|------|----------|--------|
| flake8 / ruff | Rule-based token patterns | Graph-level redundancy, dead paths |
| pylint | AST heuristics + rules | Topological inefficiencies |
| SonarQube | Rule-based + some metrics | Graph-theoretic pass selection |
| **GraphOptim** | **Weighted CFG + graph algorithms + knapsack optimization** | — |

---

## ⚡ Quickstart

### Install

```bash
pip install graphoptim
```

### 30-Second Demo

```python
import graphoptim as go

code = """
def process(items):
    results = []
    for item in items:
        if item > 0:
            results.append(item)
    return results
    print("unreachable")  # Dead code!
"""

# Analyze
report = go.analyze(code)
print(f"Score: {report.total_score}/100")
# → Score: 85/100

# Optimize
optimized = go.optimize(code, passes=["dead_code"])
# → Dead code removed, valid Python output
```

### CLI

```bash
# Analyze a file
graphoptim analyze myfile.py

# Analyze with detailed metrics
graphoptim analyze myfile.py --verbose

# Optimize (preview mode — no files changed)
graphoptim optimize myfile.py

# Optimize in-place (creates .bak backup)
graphoptim optimize myfile.py --inplace

# Analyze an entire project
graphoptim analyze ./src

# Run the empirical benchmark
graphoptim benchmark --samples 100 --models claude,gpt4o,gemini
```

### CLI Output Example

```
╭──────────────────────────────────────────────────╮
│ GraphOptim Analysis — myfile.py                   │
╰──────────────────────────────────────────────────╯
  Functions analyzed: 4
  Total optimization score: 62/100

process_data()       score: 45/100  ⚠ needs attention
├─ Cyclomatic complexity: 12   (threshold: 7)
├─ Dead nodes: 2               (unreachable at lines 34, 51)
├─ Betweenness bottleneck: 0.9 (line 22 is critical path bottleneck)
└─ Suggested passes: dead_code, centrality_split

validate_input()     score: 88/100  ✓ good
format_output()      score: 71/100  ~ acceptable
main()               score: 44/100  ⚠ needs attention
```

---

## 📊 How It Works

GraphOptim treats your code as a **graph problem**:

```
Source Code → AST → Control Flow Graph (CFG) → Weighted DiGraph → Analysis + Optimization
```

1. **Parse** — Builds a CFG where nodes are basic blocks, edges are control flow transitions
2. **Analyze** — Extracts 7 graph metrics (cyclomatic complexity, dead nodes, CFG diameter, avg shortest path, betweenness centrality, node/edge ratio, LOC)
3. **Detect** — Pattern detectors identify dead nodes, redundant paths, bottlenecks, deep chains
4. **Select** — A **0/1 Knapsack solver** selects the optimal subset of optimization passes within your risk budget
5. **Optimize** — Selected passes transform the AST, producing valid Python

> 📖 For full architecture details, see the [How It Works](docs/wiki/How-It-Works.md) wiki page.

---

## 🔧 Optimization Passes

| Pass | Detects | Fixes | Risk |
|------|---------|-------|------|
| `dead_code` | Unreachable code after return/raise/break | Removes dead AST nodes | Low (0.2) |
| `path_shortener` | Duplicate conditional branches | Merges identical branches | Medium (0.5) |
| `centrality` | High-betweenness bottleneck nodes | Suggests helper extraction | Medium (0.6) |

### Knapsack Pass Selection

Instead of running all passes blindly, GraphOptim uses **dynamic programming** (0/1 Knapsack) to select the optimal subset:

```python
from graphoptim.optimizer.passes.knapsack import KnapsackSelector, PassInfo

selector = KnapsackSelector(budget=0.6)  # max total risk = 0.6
result = selector.select(available_passes)
print(result.summary())
```

> 🧩 **Want to add your own pass?** See the [Adding Passes](docs/wiki/Adding-Passes.md) guide.

---

## 📈 Benchmark

GraphOptim includes a benchmark pipeline that empirically validates its core hypothesis against HumanEval and MBPP datasets using three LLM providers:

| Provider | Model | API Key Env Var |
|----------|-------|-----------------|
| Anthropic | Claude Opus 4.6 | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-5.2 | `OPENAI_API_KEY` |
| Google | Gemini 2.5 Pro | `GOOGLE_API_KEY` |

```bash
# Set API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AI..."

# Run benchmark
graphoptim benchmark --samples 100 --models claude,gpt4o,gemini
```

The benchmark produces:
- `benchmark_results.json` — Raw metrics for all functions
- `statistical_report.csv` — Mann-Whitney U test results
- `benchmark_report.md` — Human-readable findings with plots

---

## 🛠 Development

```bash
# Clone and set up
git clone https://github.com/YOUR-ORG/graphoptim.git
cd graphoptim

# Install with uv (recommended)
uv pip install -e ".[dev,benchmark]"

# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check .

# Run formatting
uv run black .

# Type checking
uv run mypy graphoptim/ --ignore-missing-imports
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributing guide.

---

## 📁 Project Structure

```
graphoptim/
├── parser/           # Source → Graph conversion
│   ├── cfg_builder   # Control Flow Graph builder
│   ├── dfg_builder   # Data Flow Graph builder
│   └── ast_utils     # AST helpers and node weighing
├── analyzer/         # Graph → Insights
│   ├── metrics       # 7 graph metric extraction
│   ├── patterns      # Structural pattern detectors
│   └── reporter      # Scored report generation
├── optimizer/        # Insights → Better Code
│   ├── passes/       # Individual optimization passes
│   │   ├── dead_code, path_shortener, centrality
│   │   └── knapsack  # 0/1 Knapsack pass selector
│   └── rewriter      # Pass orchestration + validation
├── benchmark/        # Empirical validation pipeline
├── cli.py            # Click + Rich CLI
└── config.py         # Configuration (env var loading)
```

---

## 📋 Links

| | |
|---|---|
| 📦 **PyPI** | [pypi.org/project/graphoptim](https://pypi.org/project/graphoptim/) |
| 📖 **Wiki** | [docs/wiki](docs/wiki/Home.md) |
| 🐛 **Issues** | [GitHub Issues](../../issues) |
| 📝 **Changelog** | [CHANGELOG.md](CHANGELOG.md) |
| 🔒 **Security** | [SECURITY.md](SECURITY.md) |
| 🤝 **Contributing** | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 📜 **License** | [MIT](LICENSE) |

---

## License

MIT License — See [LICENSE](LICENSE) for details.
