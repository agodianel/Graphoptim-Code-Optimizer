## Description

Brief description of the changes in this PR.

### Type of Change

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)
- [ ] 📝 Documentation update
- [ ] ♻️ Refactor (no functional changes)
- [ ] 🧪 Test additions or improvements
- [ ] 🔧 New optimization pass

## Changes Made

- Change 1
- Change 2

## Testing

- [ ] All existing tests pass (`uv run pytest tests/ -v`)
- [ ] New tests added for new functionality
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Formatting passes (`uv run black --check .`)
- [ ] Optimized output is valid Python (`ast.parse()` succeeds)

## For New Optimization Passes

If adding a new optimization pass:

- [ ] Pass has `detect()` and `fix()` methods
- [ ] Pass is registered in `PASS_REGISTRY` in `rewriter.py`
- [ ] Pass has `cost` and `benefit` attributes for knapsack selection
- [ ] At least 5 test cases in `tests/test_<pass_name>.py`
- [ ] `fix()` output passes `ast.parse()` validation
- [ ] Added to the passes table in `README.md`
- [ ] Added to `CHANGELOG.md`

## Screenshots / CLI Output (if applicable)

```
# Paste graphoptim analyze/optimize output here
```

## Related Issues

Closes #
