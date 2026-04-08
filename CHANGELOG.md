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
  - Dead code elimination pass (AST-based + CFG-based detection)
  - Redundant path merger pass (AST structural hashing)
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

### Security

- Code analysis uses `ast.parse()` only — no arbitrary code execution
- File operations create `.bak` backups before in-place modification
- API keys loaded from environment variables, never persisted or logged
