# Contributing Guide

<!-- auto-updated: version from src/nines/__init__.py -->

Thank you for contributing to NineS! This guide covers development setup, testing, code style, and the PR workflow.

---

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git

### Clone and Install

```bash
git clone https://github.com/YoRHa-Agents/NineS.git
cd NineS
uv sync
```

This installs NineS in editable mode with all development dependencies (pytest, ruff, mypy).

### Verify Setup

```bash
make test      # Run all tests
make lint      # Check code style
make typecheck # Run type checker
```

---

## Running Tests

NineS uses pytest with the following structure:

```
tests/
├── conftest.py              # Shared fixtures, temp directories, mock factories
├── test_core_*.py           # Core module tests
├── test_eval_*.py           # Evaluation tests
├── test_collector_*.py      # Collector tests
├── test_analyzer_*.py       # Analyzer tests
├── test_iteration_*.py      # Self-iteration tests
├── test_sandbox_*.py        # Sandbox tests
├── test_skill_*.py          # Skill adapter tests
├── test_cli_*.py            # CLI command tests
└── integration/
    ├── test_eval_e2e.py     # End-to-end evaluation
    ├── test_collect_analyze.py
    ├── test_iteration_cycle.py
    └── test_sandbox_isolation.py
```

### Run All Tests

```bash
make test
```

### Run Specific Tests

```bash
# Run a single test file
uv run pytest tests/test_eval_runner.py -v

# Run tests matching a pattern
uv run pytest -k "test_scorer" -v

# Run with coverage
make coverage
```

### Test Coverage Report

```bash
make coverage
# Generates htmlcov/index.html
```

!!! note "Mandatory Verification"
    All new features and bug fixes must include tests. Never skip or mark tests as "todo" to bypass coverage requirements.

---

## Code Style

NineS enforces consistent style via [ruff](https://docs.astral.sh/ruff/):

### Linting

```bash
make lint
```

Ruff checks enabled:

| Rule Set | Description |
|----------|-------------|
| E | pycodestyle errors |
| F | pyflakes |
| W | pycodestyle warnings |
| I | isort (import ordering) |
| N | pep8-naming |
| UP | pyupgrade |
| B | flake8-bugbear |
| A | flake8-builtins |
| SIM | flake8-simplify |
| TCH | flake8-type-checking |

### Formatting

```bash
make format
```

Configuration (`pyproject.toml`):

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.format]
quote-style = "double"
```

### Type Checking

```bash
make typecheck
```

NineS uses `mypy` in strict mode:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

---

## PR Workflow

### Branch Naming

Use descriptive branch names:

```
feature/add-semantic-search
fix/sandbox-pollution-detection
docs/update-architecture-overview
refactor/eval-runner-pipeline
```

!!! warning "Protected Branches"
    Never push directly to `main`, `master`, `yc_dev`, or `production`. Always create a feature branch and submit a PR/MR.

### Commit Messages

Follow conventional commit style:

```
feat: add semantic search to knowledge index
fix: resolve sandbox env var leak in pollution detector
docs: update CLI reference with new iterate options
refactor: extract scorer registry from eval runner
test: add integration tests for MAPIM cycle
```

### PR Checklist

Before submitting a PR:

- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] New code has tests
- [ ] Documentation is updated if behavior changed
- [ ] No silent failures — every `except` block logs or re-raises

### Review Process

1. Create a feature branch from `main`
2. Make your changes with tests
3. Push and create a PR
4. Address review feedback
5. Maintain passing CI checks
6. Merge after approval

---

## Module Ownership

When contributing to a specific module, understand its dependency rules:

| Module | Can Import From | Cannot Import From |
|--------|----------------|-------------------|
| `core/` | (nothing) | Everything else |
| `eval/` | `core/` | `collector/`, `analyzer/`, `iteration/` |
| `collector/` | `core/` | `eval/`, `analyzer/`, `iteration/` |
| `analyzer/` | `core/` | `eval/`, `collector/`, `iteration/` |
| `iteration/` | `core/`, `eval/` | `collector/`, `analyzer/` |
| `orchestrator/` | All vertex modules, `core/` | `cli/`, `skill/` |
| `sandbox/` | `core/` | Everything else |
| `skill/` | `core/` | Everything else |
| `cli/` | All modules | (none — composition root) |

---

## Error Handling Guidelines

NineS enforces a strict "no silent failures" policy:

1. **No bare `except: pass`** — Every caught exception must be logged, re-raised, or produce an explicit error state
2. **Use typed exceptions** — All errors derive from `NinesError` with structured fields (`code`, `message`, `hint`)
3. **Per-item isolation** — Single task/file failures must not abort batch operations
4. **Retry transient errors** — HTTP 429/500/502/503 get up to 3 retries with exponential backoff

---

## Make Targets

| Target | Description |
|--------|-------------|
| `make test` | Run all tests with pytest |
| `make lint` | Run ruff linter |
| `make format` | Auto-format with ruff |
| `make typecheck` | Run mypy strict type checking |
| `make coverage` | Generate test coverage report |
| `make clean` | Remove build artifacts and caches |
