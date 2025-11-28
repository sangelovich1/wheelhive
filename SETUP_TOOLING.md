# Development Tooling Setup Guide

This guide covers the development tools and CI pipeline for WheelHive.

## Overview

| Tool | Purpose | When It Runs |
|------|---------|--------------|
| `ruff` | Linting and formatting | Manual / CI |
| `mypy` | Type checking | Manual / CI |
| `unittest` | Unit tests | Manual / CI |
| `coverage` | Test coverage | Manual / CI |
| GitHub Actions | Automated CI | On push/PR to main |

## Quick Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install dev tools
pip install ruff mypy coverage types-requests types-python-dateutil types-tabulate
```

## Local Development

### Run Validation Checks

```bash
# Syntax + type checking
./check.sh

# Unit tests
./unittests.sh

# Unit tests with coverage
./unittests.sh --coverage
```

### Manual Tool Usage

```bash
# Ruff - Linting
ruff check src/ scripts/
ruff check --fix src/ scripts/  # Auto-fix issues

# Ruff - Formatting
ruff format src/ scripts/

# Mypy - Type checking
mypy src/ scripts/

# Tests
python -m unittest discover -s tests -p '*_test.py' -v

# Coverage
coverage run -m unittest discover -s tests -p '*_test.py'
coverage report -m
coverage html  # Generate HTML report in htmlcov/
```

## CI Pipeline (GitHub Actions)

Every push to `main` and every PR automatically runs:

1. **Syntax check** - Validates all Python files compile
2. **Type check** - Runs mypy on src/ and scripts/
3. **Unit tests** - Runs all tests with coverage
4. **Coverage report** - Shows test coverage percentage

### View CI Results

- **Actions tab**: https://github.com/sangelovich1/wheelhive/actions
- **Commit status**: Green ✓ or red ✗ next to each commit
- **Job summary**: Click into any run to see detailed results

### CI Badge

Add to README:
```markdown
![CI](https://github.com/sangelovich1/wheelhive/actions/workflows/ci.yml/badge.svg)
```

## Configuration

All tool configuration is in `pyproject.toml`:

- `[tool.ruff]` - Linting rules and formatting
- `[tool.mypy]` - Type checking settings
- `[tool.coverage]` - Coverage settings
- `[tool.bandit]` - Security checks

### Customize Ruff Rules

```toml
[tool.ruff.lint]
ignore = [
    "E501",    # Line too long
    "PLR0913", # Too many arguments
]

[tool.ruff.lint.per-file-ignores]
"scripts/**/*.py" = ["T201"]  # Allow print in scripts
```

## Workflow Summary

### Daily Development
```bash
# 1. Make changes
# 2. Run local checks (optional but recommended)
./check.sh

# 3. Commit and push
git add .
git commit -m "Your message"
git push

# 4. CI runs automatically on GitHub
# 5. Check results in Actions tab
```

### Before Important Releases
```bash
# Full validation
./check.sh
./unittests.sh --coverage
ruff check --fix src/ scripts/
ruff format src/ scripts/
```

## Troubleshooting

### "mypy: command not found"
```bash
pip install mypy types-requests types-python-dateutil types-tabulate
```

### "ruff: command not found"
```bash
pip install ruff
```

### CI failing but local passes
- Check Python version matches (3.12)
- Ensure all dependencies in requirements.txt
- Check CI logs for specific error

## Additional Resources

- **Ruff docs:** https://docs.astral.sh/ruff/
- **Mypy docs:** https://mypy.readthedocs.io/
- **GitHub Actions:** https://docs.github.com/en/actions
