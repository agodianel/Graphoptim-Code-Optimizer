# Quick Start Guide

## Analyze Code

### Python API

```python
import graphoptim as go

# Analyze a source string
code = """
def process_data(items):
    results = []
    for item in items:
        if item is None:
            continue
        if item > 100:
            results.append(item * 2)
        elif item > 50:
            results.append(item * 1.5)
        else:
            results.append(item)
    return results
    print("dead code")  # Unreachable
"""

report = go.analyze(code)
print(f"Score: {report.total_score}/100")

for func in report.functions:
    print(f"\n{func.function_name}(): {func.score}/100 {func.status}")
    print(f"  Cyclomatic complexity: {func.metrics.cyclomatic_complexity}")
    print(f"  Dead nodes: {func.metrics.dead_nodes_count}")
    print(f"  Suggested passes: {func.suggested_passes}")
```

### Analyze a File

```python
report = go.analyze_file("mymodule.py")
print(report.summary())
```

### Analyze a Project

```python
reports = go.analyze_project("./src")
for report in reports:
    if report.total_score < 70:
        print(f"⚠ {report.filepath}: {report.total_score}/100")
```

## Optimize Code

### Preview (Dry Run)

```python
optimized = go.optimize(code)
print(optimized)  # Dead code removed
```

### Choose Specific Passes

```python
optimized = go.optimize(code, passes=["dead_code"])
optimized = go.optimize(code, passes=["dead_code", "path_shortener"])
```

### With Budget Control

```python
optimized = go.optimize(
    code,
    budget={"max_changes": 5, "min_improvement": 0.1}
)
```

### Optimize File In-Place

```python
# Creates automatic .bak backup
go.optimize_file("mymodule.py", inplace=True)
```

### Optimize to New File

```python
go.optimize_file("mymodule.py", output="mymodule_optimized.py")
```

## CLI Usage

```bash
# Analyze
graphoptim analyze myfile.py
graphoptim analyze myfile.py --verbose
graphoptim analyze ./src --format json --output report.json

# Optimize
graphoptim optimize myfile.py                    # Dry run (preview)
graphoptim optimize myfile.py --inplace          # Modify in-place
graphoptim optimize myfile.py -o output.py       # Write to new file
graphoptim optimize myfile.py -p dead_code       # Specific pass

# Benchmark (requires API keys)
graphoptim benchmark --samples 20 --models claude

# Configuration
graphoptim config show
```

## Understanding Scores

| Score     | Status             | Meaning                           |
|-----------|--------------------|-----------------------------------|
| 80 - 100  | ✓ good             | Clean, well-structured code       |
| 60 - 79   | ~ acceptable       | Minor improvements possible       |
| 0 - 59    | ⚠ needs attention  | Significant structural issues     |

Scoring factors:
- **Cyclomatic complexity** > 7: Up to -30 points
- **Dead nodes**: -15 per unreachable block
- **Bottleneck nodes**: -10 per high-centrality node
- **Deep chains**: -8 per overly deep path
- **Redundant paths**: -12 per duplicate branch
