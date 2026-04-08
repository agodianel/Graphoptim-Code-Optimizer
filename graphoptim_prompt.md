# GraphOptim — AI Code Structural Optimizer
### Claude Code Development Prompt

---

## Project Vision

Build **GraphOptim** — an open-source Python library (published on PyPI) that parses AI-generated code into weighted graph representations and applies graph-theoretic optimization algorithms to detect and fix structural inefficiencies that rule-based linters cannot catch.

The library targets developers and teams who heavily use LLM coding assistants (Copilot, Claude, Cursor, Gemini) and need a **post-processing optimization layer** that understands code as a graph, not just as text or AST tokens.

---

## Core Hypothesis (Validate First)

> AI-generated code contains graph-level structural inefficiencies — redundant paths, inflated cyclomatic complexity, dead nodes, and over-centralized call chains — that rule-based linters (flake8, pylint, ruff) systematically miss because they operate on token/rule patterns, not graph topology.

This hypothesis must be benchmarked empirically before the tool is published. The benchmark pipeline is **part of the library** itself — users can run it against their own codebases.

---

## Phase 0 — Empirical Benchmark (Build This First)

Before building the optimizer, validate the hypothesis with a rigorous benchmark.

### Dataset Collection

1. Download the **HumanEval** dataset (OpenAI, 164 problems) from `openai/human-eval` on GitHub
2. Download **MBPP** (Google, 500 problems) from `google-research-datasets/mbpp`
3. Select 100 problems that have a clean, single-function human reference solution
4. For each problem, generate an LLM solution using three models via API:
   - **Claude** (via Anthropic API — `claude-opus-4-5` or latest)
   - **GPT-4o** (via OpenAI API)
   - **Gemini 1.5 Pro** (via Google Generative AI API)
5. Use the same prompt for all models:
   ```
   Write a Python function that solves the following problem. Return only the function code, no explanations.
   [problem description]
   ```
6. Store all solutions in a structured JSON dataset: `benchmark_dataset.json`

### CFG Extraction Pipeline

For each function (human + 3 LLM variants), extract the following:

```python
# Required libraries:
# pip install radon staticfg networkx scipy pandas matplotlib ast-comments

import ast
import networkx as nx
from radon.complexity import cc_visit
from radon.metrics import h_visit  # Halstead metrics
from staticfg import CFGBuilder

def extract_cfg_metrics(source_code: str, func_name: str) -> dict:
    """
    Parse source → CFG → weighted DiGraph → extract graph metrics.
    Returns a dict of all measurable graph properties.
    """
    # Build CFG
    cfg = CFGBuilder().build_from_src(func_name, source_code)
    G = nx.DiGraph()
    for block in cfg:
        for exit_ in block.exits:
            G.add_edge(block.id, exit_.target.id, weight=1)

    N = G.number_of_nodes()
    E = G.number_of_edges()
    CC = E - N + 2  # McCabe cyclomatic complexity

    # Dead node detection: nodes with in-degree=0 that are not the entry node
    entry = list(nx.topological_sort(G))[0] if nx.is_directed_acyclic_graph(G) else None
    dead_nodes = [n for n in G.nodes if G.in_degree(n) == 0 and n != entry]

    # Shortest / longest path (critical path)
    try:
        avg_path = nx.average_shortest_path_length(G)
        diameter = nx.diameter(G.to_undirected()) if nx.is_connected(G.to_undirected()) else None
    except Exception:
        avg_path = None
        diameter = None

    # Centrality
    betweenness = nx.betweenness_centrality(G)
    max_betweenness = max(betweenness.values()) if betweenness else 0

    # Radon metrics
    cc_results = cc_visit(source_code)
    radon_cc = cc_results[0].complexity if cc_results else CC

    return {
        "nodes": N,
        "edges": E,
        "cyclomatic_complexity": radon_cc,
        "dead_nodes_count": len(dead_nodes),
        "avg_shortest_path": avg_path,
        "cfg_diameter": diameter,
        "max_betweenness_centrality": max_betweenness,
        "node_edge_ratio": E / N if N > 0 else 0,
        "lines_of_code": len([l for l in source_code.split('\n') if l.strip()])
    }
```

### Metrics to Collect Per Function

| Metric | Formula | What it detects |
|---|---|---|
| Cyclomatic Complexity | `E - N + 2P` | Overall branching density |
| Dead Nodes | In-degree=0, not entry | Unreachable code blocks |
| CFG Diameter | Longest shortest path | Unnecessarily deep execution chains |
| Avg Shortest Path | Mean over all node pairs | Execution efficiency |
| Max Betweenness Centrality | Node bottleneck score | Over-centralized functions |
| Node/Edge Ratio | E/N | Branching density |
| Lines of Code | Non-blank lines | Verbosity |

### Statistical Analysis

For each metric, run **Mann-Whitney U test** (non-parametric) between human and each LLM group:

```python
from scipy.stats import mannwhitneyu, kruskal
import pandas as pd

def run_statistical_tests(df: pd.DataFrame) -> pd.DataFrame:
    metrics = ['cyclomatic_complexity', 'dead_nodes_count', 'avg_shortest_path',
               'cfg_diameter', 'max_betweenness_centrality', 'lines_of_code']
    results = []
    for metric in metrics:
        human = df[df['source'] == 'human'][metric].dropna()
        for model in ['claude', 'gpt4o', 'gemini']:
            llm = df[df['source'] == model][metric].dropna()
            stat, p = mannwhitneyu(human, llm, alternative='two-sided')
            results.append({
                'metric': metric,
                'model': model,
                'human_median': human.median(),
                'llm_median': llm.median(),
                'p_value': p,
                'significant': p < 0.05
            })
    return pd.DataFrame(results)
```

### Benchmark Output

Produce:
- `benchmark_results.json` — raw metrics for all 400 functions
- `statistical_report.csv` — test results per metric/model pair
- `benchmark_report.md` — human-readable findings with plots

This benchmark becomes the **scientific foundation** of the library and a key part of the README.

---

## Phase 1 — Core Library Architecture

### Package Name and Structure

```
graphoptim/
├── __init__.py
├── parser/
│   ├── __init__.py
│   ├── cfg_builder.py         # AST → CFG → NetworkX DiGraph
│   ├── dfg_builder.py         # Data Flow Graph builder
│   └── ast_utils.py           # AST helpers and node weighers
├── analyzer/
│   ├── __init__.py
│   ├── metrics.py             # Graph metric extraction
│   ├── patterns.py            # Pattern detectors (dead nodes, redundant paths, etc.)
│   └── reporter.py            # Human-readable report generator
├── optimizer/
│   ├── __init__.py
│   ├── passes/
│   │   ├── dead_code.py       # Dead node elimination
│   │   ├── path_shortener.py  # Redundant branch merging
│   │   ├── centrality.py      # Over-centralized node splitting
│   │   └── knapsack.py        # Optimal pass selection via 0/1 knapsack
│   └── rewriter.py            # Graph changes → code AST rewrite
├── benchmark/
│   ├── __init__.py
│   ├── collector.py           # Dataset downloader and LLM solution generator
│   ├── runner.py              # Full benchmark pipeline runner
│   └── report.py              # Statistical analysis and report generation
├── cli.py                     # Command-line interface
└── config.py                  # Configuration dataclasses
```

### Public API Design

The library must have a clean, minimal API. Three main entry points:

#### 1. Analyze — Read-only inspection

```python
import graphoptim as go

# Analyze a single function
report = go.analyze(source_code)
print(report.cyclomatic_complexity)  # int
print(report.dead_nodes)             # List[DeadNode]
print(report.redundant_paths)        # List[RedundantPath]
print(report.bottlenecks)            # List[BottleneckNode]
print(report.score)                  # 0-100 optimization score
print(report.summary())              # human-readable string

# Analyze a whole file
file_report = go.analyze_file("mymodule.py")
for func_report in file_report.functions:
    print(func_report.function_name, func_report.score)

# Analyze a whole directory
project_report = go.analyze_project("./src")
```

#### 2. Optimize — Apply fixes

```python
# Optimize and return improved source code
optimized_code = go.optimize(source_code)

# With configuration — choose which passes to apply
optimized_code = go.optimize(
    source_code,
    passes=["dead_code", "path_shortener"],   # explicit passes
    budget={"max_changes": 5, "min_improvement": 0.1}  # knapsack budget
)

# Optimize a file in-place (creates .bak backup)
go.optimize_file("mymodule.py", inplace=True)

# Optimize all files in a project
go.optimize_project("./src", output_dir="./src_optimized")
```

#### 3. Benchmark — Run the empirical study

```python
from graphoptim.benchmark import Benchmark

bm = Benchmark(
    anthropic_api_key="...",
    openai_api_key="...",
    google_api_key="...",
    n_samples=100,
    dataset="humaneval"  # or "mbpp"
)

results = bm.run()
results.save("my_benchmark_results/")
results.show_report()  # opens HTML report
```

---

## Phase 2 — Optimization Passes

### Pass 1: Dead Code Elimination

**Detection:** Nodes in the CFG with `in_degree == 0` that are not the function entry point.

**Fix:** Remove the corresponding AST nodes from the source.

```python
class DeadCodePass:
    def detect(self, cfg: nx.DiGraph, ast_tree: ast.AST) -> List[DeadNode]:
        """Find unreachable code blocks."""
        ...

    def fix(self, ast_tree: ast.AST, dead_nodes: List[DeadNode]) -> ast.AST:
        """Remove dead AST nodes."""
        ...
```

### Pass 2: Redundant Path Merger

**Detection:** Two or more paths in the CFG that:
- Start and end at the same nodes
- Have identical or equivalent intermediate operations
- Represent duplicate conditional branches

**Algorithm:** Build a path matrix, compare path fingerprints (hash of AST node sequence), flag duplicates.

**Fix:** Merge duplicate branches into a single path, possibly extracting the shared logic into a helper.

### Pass 3: Critical Path Optimizer (Shortest Path)

**Detection:** Functions where the **critical execution path** (longest weighted path in the CFG) is unnecessarily long due to sequential operations that could be restructured.

**Algorithm:**
- Weight edges by estimated operation cost (I/O ops = high weight, arithmetic = low weight)
- Find the critical path using longest-path algorithm on DAG
- Suggest reordering or early-exit insertions

### Pass 4: Betweenness Centrality Decomposition

**Detection:** Nodes with `betweenness_centrality > threshold` (default: 0.7) — these are bottleneck nodes that every execution path passes through, indicating the function is over-centralized.

**Fix:** Suggest extracting the bottleneck node's logic into a helper function to improve testability and reusability.

### Pass 5: Knapsack Pass Selector

**This is the key innovation.** Given a set of available optimization passes, each with:
- `cost`: estimated code change risk (0.0 to 1.0)
- `benefit`: estimated complexity reduction (0.0 to 1.0)
- `prerequisites`: passes that must run first

Solve the **0/1 Knapsack problem** to select the optimal subset of passes within a user-defined budget:

```python
from graphoptim.optimizer.passes.knapsack import KnapsackSelector

selector = KnapsackSelector(budget=0.6)  # max total risk = 0.6
available_passes = [dead_code_pass, path_merger, critical_path, centrality]

# Returns the optimal subset maximizing total benefit within budget
selected = selector.select(available_passes, current_metrics)
```

**Algorithm:** Dynamic programming O(n·W) knapsack where:
- n = number of available passes
- W = budget (discretized into integer units, e.g., 0.6 → 60)

---

## Phase 3 — CLI Interface

The CLI is a first-class citizen. Users should be able to use graphoptim without writing Python.

```bash
# Install
pip install graphoptim

# Analyze a file
graphoptim analyze myfile.py

# Analyze with detailed output
graphoptim analyze myfile.py --verbose --output report.html

# Optimize a file (preview only)
graphoptim optimize myfile.py --dry-run

# Optimize in place
graphoptim optimize myfile.py --inplace

# Optimize a whole project
graphoptim optimize ./src --output ./src_optimized

# Run the benchmark (requires API keys)
graphoptim benchmark --samples 100 --models claude,gpt4o,gemini

# Show config
graphoptim config show

# Set API keys
graphoptim config set anthropic_api_key sk-ant-...
```

CLI output example for `graphoptim analyze myfile.py`:

```
GraphOptim Analysis — myfile.py
═══════════════════════════════════════
Functions analyzed: 4
Total optimization score: 62/100

function: process_data()         score: 45/100  ⚠ needs attention
  ├─ Cyclomatic complexity: 12   (threshold: 7)
  ├─ Dead nodes: 2               (unreachable branches at lines 34, 51)
  ├─ Betweenness bottleneck: 0.9 (line 22 is critical path bottleneck)
  └─ Suggested passes: dead_code, centrality_split

function: validate_input()       score: 88/100  ✓ good
function: format_output()        score: 71/100  ~ acceptable
function: main()                 score: 44/100  ⚠ needs attention

Run `graphoptim optimize myfile.py` to apply fixes.
```

---

## Phase 4 — PyPI Publication

### `pyproject.toml` configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "graphoptim"
version = "0.1.0"
description = "Graph-theoretic optimizer for AI-generated Python code"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
keywords = ["ai", "code-optimization", "graph-theory", "static-analysis", "llm"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Quality Assurance",
    "Programming Language :: Python :: 3.9",
]
dependencies = [
    "networkx>=3.0",
    "radon>=6.0",
    "staticfg>=0.1",
    "scipy>=1.10",
    "pandas>=2.0",
    "rich>=13.0",          # Beautiful CLI output
    "click>=8.0",          # CLI framework
    "anthropic>=0.25",     # Claude API (optional, for benchmark)
    "openai>=1.0",         # OpenAI API (optional, for benchmark)
    "google-generativeai>=0.5", # Gemini API (optional, for benchmark)
]

[project.optional-dependencies]
benchmark = ["anthropic", "openai", "google-generativeai", "matplotlib", "seaborn"]
dev = ["pytest", "black", "ruff", "mypy"]

[project.scripts]
graphoptim = "graphoptim.cli:main"
```

### README Must Include

1. **The benchmark results** — concrete numbers: "LLM-generated code has X% higher cyclomatic complexity, Y% more dead nodes"
2. **A 30-second quickstart** — install → analyze → optimize
3. **How graph theory applies** — one clear diagram showing CFG nodes/edges
4. **Comparison table** with existing tools (flake8, pylint, ruff) showing what GraphOptim catches that they miss
5. **CI badge** and **PyPI version badge**

---

## Phase 5 — Testing Strategy

### Unit Tests

Every optimization pass must have unit tests with known-bad and known-good Python snippets:

```python
# tests/test_dead_code_pass.py
def test_dead_code_detected():
    code = """
def foo(x):
    if x > 0:
        return x
    return -x
    print("never reached")  # dead code
"""
    report = go.analyze(code)
    assert report.dead_nodes_count == 1
    assert report.dead_nodes[0].line == 7

def test_dead_code_eliminated():
    optimized = go.optimize(code, passes=["dead_code"])
    assert "never reached" not in optimized
```

### Integration Tests

- Run analyze + optimize on real Python stdlib functions
- Verify that optimized code is syntactically valid (`ast.parse()` must not raise)
- Verify that optimized code passes the original function's tests (where available from HumanEval)

### Regression Tests

- Store 20 known problematic AI-generated snippets
- After every change, verify all 20 are still correctly detected and optimized

---

## Development Environment Setup

```bash
# Clone and set up
git clone https://github.com/<your-org>/graphoptim
cd graphoptim
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,benchmark]"

# API keys for benchmark (set in environment)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AI..."

# Run tests
pytest tests/ -v

# Run benchmark (generates benchmark_results/)
graphoptim benchmark --samples 20 --models claude  # start small

# Build and check package
python -m build
twine check dist/*
```

---

## Prioritized Build Order

| Step | What to build | Done when |
|---|---|---|
| 1 | `parser/cfg_builder.py` — CFG from Python source | CFG of a 10-line function has correct nodes/edges |
| 2 | `analyzer/metrics.py` — extract all 7 metrics | Metrics match radon's output for CC |
| 3 | `benchmark/collector.py` — download HumanEval, call APIs | 100 function pairs collected and stored as JSON |
| 4 | `benchmark/runner.py` — run metrics + stats | Statistical report shows p-values per metric |
| 5 | `optimizer/passes/dead_code.py` | Dead code removed from 5 test cases |
| 6 | `optimizer/passes/knapsack.py` | Pass selector returns optimal subset |
| 7 | `optimizer/rewriter.py` — graph edits → code | Output is valid Python (`ast.parse()` passes) |
| 8 | `cli.py` — `analyze` and `optimize` commands | CLI works end-to-end on a real file |
| 9 | PyPI publish | `pip install graphoptim` works |
| 10 | `benchmark` CLI command | Users can reproduce the benchmark |

---

## Key Design Constraints

- **Never break working code.** The optimizer must produce syntactically valid, semantically equivalent code. When unsure, emit a warning and skip the pass rather than risking a bad rewrite.
- **Preserve docstrings and comments.** AST rewrites must carry through all decorators, docstrings, and inline comments.
- **Dry-run by default.** `optimize()` returns the new code as a string; it never writes to disk unless explicitly asked via `optimize_file(inplace=True)`.
- **Graceful degradation.** If `staticfg` fails to parse a function (e.g., async functions, complex decorators), fall back to AST-only metrics rather than crashing.
- **Python-first, language-agnostic design.** The `parser/` and `optimizer/` modules should be designed so that a future `graphoptim-js` or `graphoptim-rs` package can follow the same architecture.

---

## Differentiation from Existing Tools

| Tool | Approach | Misses |
|---|---|---|
| flake8 / ruff | Rule-based token patterns | Graph-level redundancy, dead paths |
| pylint | AST heuristics + rules | Topological inefficiencies |
| Graphify | CFG visualization only | No optimization, no metrics |
| SonarQube | Rule-based + some metrics | No graph-theoretic pass selection |
| **GraphOptim** | **Weighted CFG + graph algorithms + knapsack pass selection** | — |

---

*This document is the complete specification for GraphOptim v0.1. Start with Phase 0 (benchmark) — the empirical results will validate the core hypothesis and form the scientific credibility of the library.*
