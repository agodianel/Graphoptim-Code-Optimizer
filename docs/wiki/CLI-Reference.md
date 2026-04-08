# CLI Reference

GraphOptim provides a full-featured command-line interface.

## Global Options

```
graphoptim --version    Show version
graphoptim --help       Show help
```

---

## `graphoptim analyze`

Read-only code inspection.

```
graphoptim analyze PATH [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `PATH` | Python file or directory to analyze |

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--verbose`, `-v` | `false` | Show detailed output including node/edge counts |
| `--output`, `-o` | — | Save report to file |
| `--format` | `text` | Output format: `text` or `json` |
| `--threshold` | `0.7` | Betweenness centrality threshold |

**Examples:**

```bash
# Analyze a single file
graphoptim analyze myfile.py

# Verbose analysis with all metrics
graphoptim analyze myfile.py --verbose

# JSON output
graphoptim analyze myfile.py --format json

# Save report to file
graphoptim analyze myfile.py -o report.txt

# Analyze entire project
graphoptim analyze ./src --verbose
```

---

## `graphoptim optimize`

Apply graph-theoretic optimization passes.

```
graphoptim optimize PATH [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `PATH` | Python file or directory to optimize |

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | `true` | Preview only (default) |
| `--inplace` | `false` | Modify file in-place (creates .bak backup) |
| `--output`, `-o` | — | Write optimized code to file/directory |
| `--passes`, `-p` | auto | Comma-separated list of passes |
| `--budget` | `0.6` | Risk budget for knapsack selection (0.0-1.0) |

**Available Passes:**
| Pass Name | Description |
|-----------|-------------|
| `dead_code` | Remove unreachable code |
| `path_shortener` | Merge duplicate branches |
| `centrality` | Add advisory comments at bottlenecks |

**Examples:**

```bash
# Preview optimization
graphoptim optimize myfile.py

# Apply specific passes
graphoptim optimize myfile.py -p dead_code,path_shortener --inplace

# Optimize with low-risk budget
graphoptim optimize myfile.py --budget 0.3 --inplace

# Optimize to new directory
graphoptim optimize ./src -o ./src_optimized
```

---

## `graphoptim benchmark`

Run the empirical benchmark study.

```
graphoptim benchmark [OPTIONS]
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--samples`, `-n` | `100` | Number of benchmark problems |
| `--models`, `-m` | `claude,gpt4o,gemini` | Comma-separated model list |
| `--dataset` | `humaneval` | Dataset: `humaneval` or `mbpp` |
| `--output-dir`, `-o` | `benchmark_results` | Output directory |

**Required Environment Variables:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AI..."
```

**Examples:**

```bash
# Quick benchmark with Claude only
graphoptim benchmark --samples 20 --models claude

# Full benchmark
graphoptim benchmark --samples 100 --models claude,gpt4o,gemini

# Using MBPP dataset
graphoptim benchmark --dataset mbpp --samples 50
```

---

## `graphoptim config`

Show or set configuration.

```
graphoptim config ACTION [KEY] [VALUE]
```

**Actions:**
| Action | Description |
|--------|-------------|
| `show` | Display current configuration |
| `set` | Set a configuration value |

**Examples:**

```bash
# Show all settings and API key status
graphoptim config show

# Set an API key (suggests using env vars)
graphoptim config set anthropic_api_key sk-ant-...
```
