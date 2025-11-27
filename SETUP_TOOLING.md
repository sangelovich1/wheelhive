# Development Tooling Setup Guide

This guide walks you through setting up the development tooling for this project, including `ruff`, `mypy`, and `pre-commit` hooks.

## Overview

We use modern Python development tools:

- **`pyproject.toml`** - Centralized configuration for all tools
- **`ruff`** - Fast linter and formatter (replaces black, isort, flake8)
- **`mypy`** - Static type checker
- **`pre-commit`** - Automated checks before each commit
- **`pytest`** - Unit testing with coverage
- **`bandit`** - Security linter

## Quick Setup

```bash
# 1. Install development dependencies
pip install -r requirements.txt
pip install ruff pre-commit pytest-cov bandit[toml]

# 2. Install pre-commit hooks
pre-commit install

# 3. Run hooks on all files (first time)
pre-commit run --all-files
```

That's it! Now the tools will run automatically on every commit.

## Manual Tool Usage

### Ruff - Linting and Formatting

```bash
# Check for issues (no changes)
ruff check .

# Fix issues automatically
ruff check --fix .

# Format code
ruff format .

# Check + format in one go
ruff check --fix . && ruff format .
```

**Configuration:** See `[tool.ruff]` in `pyproject.toml`

**What it does:**

- Enforces PEP 8 style
- Sorts imports (isort)
- Finds bugs (pyflakes, flake8-bugbear)
- Modernizes Python syntax (pyupgrade)
- Simplifies code (flake8-simplify)
- ~10-100x faster than black + flake8 + isort combined

### Mypy - Type Checking

```bash
# Check types in src and scripts
mypy src/ scripts/

# Check specific file
mypy src/bot.py

# Count warnings (track progress)
mypy src/ scripts/ 2>&1 | grep "error:" | wc -l
```

**Configuration:** See `[tool.mypy]` in `pyproject.toml`

**Current status:**

- Target: 0 warnings in our codebase
- Current: ~36 warnings (down from 626 total including third-party libs)

### Pre-commit - Automated Checks

```bash
# Run on staged files (automatic on commit)
pre-commit run

# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
pre-commit run mypy --all-files

# Skip hooks for emergency commit (use sparingly!)
git commit --no-verify -m "Emergency fix"

# Update hook versions
pre-commit autoupdate
```

**Configuration:** See `.pre-commit-config.yaml`

**Hooks enabled:**

1. **ruff** - Linting with auto-fix
2. **ruff-format** - Code formatting
3. **mypy** - Type checking (src/ and scripts/ only)
4. **check-yaml/toml/json** - File syntax validation
5. **check-ast** - Python syntax validation
6. **trailing-whitespace** - Remove trailing spaces
7. **end-of-file-fixer** - Ensure newline at EOF
8. **debug-statements** - No debugger/breakpoint statements
9. **bandit** - Security vulnerability checks
10. **markdownlint** - Markdown formatting (docs)

### Pytest - Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/trade_test.py

# Run tests matching pattern
pytest -k "test_parse"

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"

# Generate HTML coverage report
pytest --cov=src --cov-report=html
# View: open htmlcov/index.html
```

**Configuration:** See `[tool.pytest.ini_options]` in `pyproject.toml`

### Bandit - Security Checks

```bash
# Check for security issues
bandit -r src/ scripts/

# Use config from pyproject.toml
bandit -c pyproject.toml -r src/ scripts/
```

**Configuration:** See `[tool.bandit]` in `pyproject.toml`

## Integration with Existing Workflow

### Before (Old Workflow)

```bash
# Manual checks before commit
./check.sh              # mypy + syntax
./unittests.sh          # pytest
# (manually format code)
git add .
git commit -m "message"
```

### After (New Workflow)

```bash
# Edit code
vim src/bot.py

# Optional: Run ruff to fix issues before staging
ruff check --fix . && ruff format .

# Stage changes
git add .

# Commit (pre-commit runs automatically!)
git commit -m "message"
# ✓ ruff checks and fixes issues
# ✓ ruff formats code
# ✓ mypy checks types
# ✓ All file checks pass
# → Commit succeeds if all pass

# If hooks fail, fix issues and try again
# (hooks show exactly what failed)
```

**Benefits:**

- Automated - no manual `./check.sh` needed
- Faster feedback - catches issues before commit
- Consistent - everyone on team gets same checks
- Auto-fix - ruff fixes most issues automatically

## Customization

### Disable Specific Rules

If a rule is too noisy, add to ignore list in `pyproject.toml`:

```toml
[tool.ruff.lint]
ignore = [
    "E501",    # Line too long (example)
    "PLR0913", # Too many arguments
]
```

### Per-File Overrides

```toml
[tool.ruff.lint.per-file-ignores]
"scripts/**/*.py" = [
    "T201",  # Allow print statements in scripts
]
```

### Skip Hooks Temporarily

```bash
# Skip all hooks (emergency only!)
git commit --no-verify -m "Emergency fix"

# Set SKIP environment variable
SKIP=mypy git commit -m "Skip mypy for this commit"
```

## Troubleshooting

### "ruff: command not found"

```bash
pip install ruff
# or
pip install -e ".[dev]"  # Install with dev dependencies
```

### "pre-commit: command not found"

```bash
pip install pre-commit
pre-commit install
```

### Hooks are slow

```bash
# Skip slow hooks for quick commits
SKIP=mypy git commit -m "Quick fix"

# Or adjust which hooks run in .pre-commit-config.yaml
```

### Mypy errors from third-party libraries

These are ignored in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["discord.*", "yfinance.*", ...]
ignore_missing_imports = true
```

### Ruff auto-fix broke my code

```bash
# Ruff is safe, but if issues occur:
git diff  # Review changes
git checkout -- <file>  # Revert if needed

# Report false positives: https://github.com/astral-sh/ruff/issues
```

## Best Practices

1. **Run `pre-commit run --all-files` after setup** - Ensures all existing code passes
2. **Commit small, focused changes** - Easier to fix hook failures
3. **Read hook output** - It tells you exactly what's wrong and how to fix it
4. **Use `--fix` flags** - Let tools auto-fix issues: `ruff check --fix .`
5. **Update hooks regularly** - `pre-commit autoupdate` (every few months)

## Additional Resources

- **Ruff docs:** <https://docs.astral.sh/ruff/>
- **Pre-commit docs:** <https://pre-commit.com/>
- **Mypy docs:** <https://mypy.readthedocs.io/>
- **Project config:** See `pyproject.toml` for all tool settings

## Dependencies: requirements.txt vs pyproject.toml

**TL;DR: Keep using `requirements.txt` - it's not deprecated!**

### Current Setup (Recommended)

```bash
# Install production dependencies
pip install -r requirements.txt

# Install optional RAG dependencies
pip install -r requirements-rag.txt

# Install development tools
pip install ruff pre-commit bandit[toml]
```

### Why Both Files?

- **`requirements.txt`** - Production dependencies (what to install)
  - Pinned versions for reproducibility
  - Standard pip workflow
  - Works everywhere (CI/CD, containers, etc.)

- **`pyproject.toml`** - Tool configuration (how to develop)
  - Ruff, mypy, pytest settings
  - Project metadata
  - Optional dependencies reference

### Future Migration (Optional)

If you want to switch to `pyproject.toml`-only installation:

```bash
# Option 1: Use pip-tools to sync
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt  # Generate from pyproject.toml

# Option 2: Direct install from pyproject.toml
pip install -e .           # Install project in editable mode
pip install -e ".[dev]"    # Install with dev dependencies
```

**For now, `requirements.txt` is the recommended approach.**
