# Installation

<!-- auto-updated: version from src/nines/__init__.py -->

Detailed instructions for installing NineS {{ nines_version }} across different methods and environments.

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.12+ | 3.12 |
| OS | Linux, macOS, Windows | Linux or macOS |
| RAM | 512 MB | 2 GB+ |
| Disk | 100 MB | 500 MB (with data) |

---

## Install Methods

=== "One-Click Script (Fastest)"

    The `scripts/install.sh` script handles everything — Python verification, package installation, and agent skill setup:

    ```bash
    curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
    ```

    Or if you already have the repository cloned:

    ```bash
    bash scripts/install.sh --target all
    ```

    Options:

    | Flag | Description |
    |------|-------------|
    | `--target <RUNTIME>` | Agent runtime: `cursor`, `claude`, `codex`, `copilot`, `all` (default: `all`) |
    | `--global` | Install skill files to user-global directory |
    | `--no-skill` | Only install Python package, skip skill file generation |

=== "uv (Recommended)"

    [uv](https://docs.astral.sh/uv/) provides the fastest installation experience.

    ```bash
    git clone https://github.com/YoRHa-Agents/NineS.git
    cd NineS
    uv sync
    uv run nines --version
    ```

    To run NineS commands without the `uv run` prefix, activate the environment:

    ```bash
    source .venv/bin/activate
    nines --version
    ```

=== "pip (Editable)"

    Install in editable mode for development:

    ```bash
    git clone https://github.com/YoRHa-Agents/NineS.git
    cd NineS
    pip install -e .
    nines --version
    ```

=== "pip (Direct)"

    Install directly from the repository:

    ```bash
    git clone https://github.com/YoRHa-Agents/NineS.git
    cd NineS
    pip install .
    nines --version
    ```

---

## Verifying Installation

After installation, verify NineS is working:

```bash
nines --version
# nines, version {{ nines_version }}

nines --help
# Shows all available commands
```

---

## Configuration File Setup

NineS uses TOML configuration with a priority-based merge system:

1. **CLI flags** — Override everything (`--config`, `--verbose`, etc.)
2. **Project config** — `nines.toml` in the project root
3. **User config** — `~/.config/nines/config.toml`
4. **Built-in defaults** — Bundled in the package

Create a project-level configuration:

```bash
cat > nines.toml << 'EOF'
[general]
log_level = "INFO"
output_dir = "./reports"

[eval]
default_scorer = "composite"
sandbox_enabled = true

[collect]
default_limit = 50
incremental = true

[analyze]
default_depth = "standard"
decompose = true
index = true
EOF
```

!!! note "Config Discovery"
    NineS automatically discovers `nines.toml` in the current working directory or any parent directory.

---

## Environment Variables

NineS reads the following environment variables at runtime:

| Variable | Description | Example |
|----------|-------------|---------|
| `NINES_GITHUB_TOKEN` | GitHub Personal Access Token for V2 collection | `ghp_xxxxxxxxxxxx` |
| `NINES_EVAL_DEFAULT_SCORER` | Override the default scorer | `composite` |
| `NINES_COLLECT_GITHUB_TOKEN` | GitHub token (alias) | `ghp_xxxxxxxxxxxx` |
| `NINES_GENERAL_LOG_LEVEL` | Override log level | `DEBUG` |

Environment variable convention: `NINES_<SECTION>_<KEY>` in uppercase, dots become underscores.

!!! warning "Token Security"
    Never commit API tokens to version control. Use environment variables or a secrets manager. Token fields are masked in logs and error messages.

---

## Troubleshooting

### `nines: command not found`

Ensure the installation directory is on your `PATH`:

```bash
# If using uv
uv run nines --version

# If using pip, check that the scripts directory is on PATH
python -m nines.cli.main --version
```

### Python version mismatch

NineS requires Python 3.12+. Check your version:

```bash
python --version
```

If you have multiple Python versions, specify the correct one:

```bash
uv venv --python 3.12
uv sync
```

### Permission denied errors

If installing with pip globally, use a virtual environment instead:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### GitHub API rate limiting

If collection commands fail with rate limit errors:

1. Set a GitHub Personal Access Token:
   ```bash
   export NINES_GITHUB_TOKEN="ghp_your_token_here"
   ```
2. The token provides 5,000 requests/hour (vs. 60 unauthenticated)
3. NineS automatically handles rate limiting with adaptive backoff

### SQLite errors

If you encounter database errors:

```bash
# Reset the database
rm -f data/nines.db
nines collect github "test" --limit 1  # Recreates the schema
```
