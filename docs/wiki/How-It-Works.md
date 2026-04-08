# How It Works

GraphOptim treats code as a **graph problem**. This page explains the full pipeline.

## Pipeline Overview

```
Source Code → AST → Control Flow Graph (CFG) → Weighted DiGraph → Analysis → Optimization
```

### Step 1: Parse

Python source code is parsed into an Abstract Syntax Tree (AST) using Python's built-in `ast` module.

### Step 2: Build CFG

The AST is transformed into a **Control Flow Graph** — a directed graph where:

- **Nodes** = Basic blocks (sequences of statements with no branches)
- **Edges** = Control flow transitions (if/else branches, loop entries/exits, etc.)
- **Edge weights** = Estimated computational cost of the transition

```
┌─────────────┐
│ Entry Block  │
│  x = input() │
└──────┬──────┘
       │
┌──────▼──────┐
│  if x > 0   │──── False ────┐
└──────┬──────┘               │
       │ True                  │
┌──────▼──────┐        ┌──────▼──────┐
│  return x   │        │  return -x  │
└──────┬──────┘        └──────┬──────┘
       │                      │
┌──────▼──────────────────────▼──────┐
│              Exit Block             │
└────────────────────────────────────┘
```

### Step 3: Extract Metrics

Seven graph-theoretic metrics are extracted from the CFG:

| # | Metric | Formula | What It Detects |
|---|--------|---------|-----------------|
| 1 | Cyclomatic Complexity | `E - N + 2P` | Overall branching density |
| 2 | Dead Nodes | `in_degree=0 and not entry` | Unreachable code blocks |
| 3 | CFG Diameter | Longest shortest path | Deep execution chains |
| 4 | Avg Shortest Path | Mean over all pairs | Execution efficiency |
| 5 | Max Betweenness Centrality | Node bottleneck score | Over-centralized functions |
| 6 | Node/Edge Ratio | `E/N` | Branching density |
| 7 | Lines of Code | Non-blank lines | Verbosity |

### Step 4: Detect Patterns

Four pattern detectors run on the CFG:

1. **Dead Nodes** — Unreachable code after return/raise/break/continue
2. **Redundant Paths** — Duplicate conditional branches (structurally equal via AST hashing)
3. **Bottleneck Nodes** — High betweenness centrality (>0.7) indicating over-centralized code
4. **Deep Chains** — Execution paths deeper than threshold (default: 8)

### Step 5: Select Passes (Knapsack)

Available optimization passes are evaluated. Each has:
- `cost` — Risk of introducing bugs (0.0-1.0)
- `benefit` — Expected improvement (0.0-1.0)

A **0/1 Knapsack** dynamic programming solver selects the optimal subset within the user's risk budget.

### Step 6: Optimize

Selected passes transform the AST:
1. Apply each pass sequentially
2. Validate output with `ast.parse()` after each pass
3. Skip any pass that produces invalid code
4. Post-process for readability

## Data Flow Graph (DFG)

In addition to the CFG, GraphOptim builds a **Data Flow Graph** tracking variable definitions and usages. This enables:

- Detection of unused variables
- Understanding data dependencies between operations
- Future dead data flow elimination

## Architecture

```
graphoptim/
├── parser/          ← Source → Graph
│   ├── cfg_builder  ← Control Flow Graph
│   ├── dfg_builder  ← Data Flow Graph
│   └── ast_utils    ← AST helpers
├── analyzer/        ← Graph → Insights
│   ├── metrics      ← 7 graph metrics
│   ├── patterns     ← Pattern detectors
│   └── reporter     ← Scored reports
├── optimizer/       ← Insights → Better Code
│   ├── passes/      ← Individual optimizations
│   │   ├── dead_code
│   │   ├── path_shortener
│   │   ├── centrality
│   │   └── knapsack  ← Pass selection
│   └── rewriter     ← Orchestration
├── benchmark/       ← Empirical validation
├── cli.py           ← Command-line interface
└── config.py        ← Configuration
```
