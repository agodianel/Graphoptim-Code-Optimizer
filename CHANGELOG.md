# Changelog

All notable changes to GraphOptim will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-09

### Added

- **Core Parser Module**
  - Custom CFG builder from Python AST (no `staticfg` dependency)
  - Data Flow Graph (DFG) builder for variable def-use tracking
  - AST utilities: function extraction, structural hashing, operation weighting

- **Analyzer Module**
  - 7 graph metrics: cyclomatic complexity, dead nodes, CFG diameter, avg shortest path, max betweenness centrality, node/edge ratio, LOC
  - Cross-validation with `radon` for cyclomatic complexity
  - Pattern detectors: dead nodes, redundant paths, bottleneck nodes, deep chains
  - Scored reports (0-100) with human-readable summaries

- **Optimizer Module**
  - Added `guard_clause` pass to refactor deeply nested if-blocks into early-returns
  - Added `unused_variable` pass to safely prune dead assignments with pure expressions
  - Added `constant_folding` pass for deterministic static expression evaluation
  - Dead code elimination pass (AST-based + CFG-based detection)
  - Redundant path merger pass (AST strict hashing)
  - Betweenness centrality decomposition pass (advisory)
  - **0/1 Knapsack pass selector** — optimal pass selection within risk budget
  - Code rewriter with syntax validation and post-processing

- **CLI Interface**
  - `graphoptim analyze` — read-only code inspection with rich output
  - `graphoptim optimize` — apply optimization passes (dry-run by default)
  - `graphoptim benchmark` — run empirical benchmark study
  - `graphoptim config` — show/set configuration
  - Beautiful tree-style output with `rich`

- **Benchmark Pipeline**
  - HumanEval and MBPP dataset support
  - LLM solution generation via Claude Opus 4.6, GPT-5.2, Gemini 2.5 Pro
  - Mann-Whitney U statistical tests
  - Markdown report generation with visualization plots

- **Public Python API**
  - `go.analyze(source_code)` — analyze source string
  - `go.optimize(source_code)` — optimize source string
  - `go.analyze_file(path)` / `go.optimize_file(path)` — file operations
  - `go.analyze_project(dir)` / `go.optimize_project(dir)` — project operations

- **Testing**
  - 52 unit and integration tests
  - CFG builder, metrics, dead code, knapsack, rewriter, CLI tests

- **Project Infrastructure**
  - PyPI-ready packaging with `hatchling`
  - GitHub Actions CI (lint, test matrix 3.9-3.13, type check, build)
  - GitHub Actions publish workflow (trusted publishing)
  - Contributing guide with pass extension tutorial
  - Security policy
  - Code of Conduct

### Changed

- CLI `--diff` flag on a single file now automatically saves the output locally into an isolated `graphoptimized/` directory.

### Fixed

- **Critical**: `path_shortener` (`_DuplicateBranchMerger`) now uses strict `ast.unparse` hashing instead of ambiguous topological structural hashing, preventing the destructive merging of branches that only differed by constant values or variable names.
- Fixed GitHub Actions runner failure by explicitly creating native `uv` virtual environments to bypass Ubuntu's externally managed system Python blocks.
- Muted Node 20 / Action version deprecation warnings in CI pipeline.
- Resolved 30+ Pytest and MyPy strict-typing failures.

### Security

- Code analysis uses `ast.parse()` only — no arbitrary code execution
- File operations create `.bak` backups before in-place modification
- API keys loaded from environment variables, never persisted or logged
