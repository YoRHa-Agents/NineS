# NineS sample files

Ready-to-run examples for V1 evaluation tasks and project configuration.

## Layout

| Path | Purpose |
|------|---------|
| `eval/*.toml` | Single-task definitions (TOML). Run with `nines eval`. |
| `config/nines.toml` | Example **project** config. Copy to the repo root as `nines.toml` or pass `--config`. |

## Evaluation tasks (V1)

From the repository root (after `uv sync`):

```bash
uv run nines eval --tasks-path samples/eval/hello_world.toml
uv run nines eval --tasks-path samples/eval/fizzbuzz.toml
uv run nines eval --tasks-path samples/eval/sorting_algorithm.toml
```

Run all tasks in the folder:

```bash
uv run nines eval --tasks-path samples/eval
```

Optional flags (see [Quick Start](../docs/quick-start.md)):

```bash
uv run nines eval --tasks-path samples/eval/hello_world.toml --scorers composite -f markdown --output-dir ./reports
```

## Project configuration

`config/nines.toml` mirrors the shape of [defaults.toml](../src/nines/core/defaults.toml): `[eval]`, `[collect]`, `[analyze]`, `[iteration]`, `[self_eval]`, and optional `[project]` metadata. Copy it to `./nines.toml` to override defaults for this working tree, or reference it explicitly if the CLI supports `--config` / `NINES_*` overrides.

Unknown keys are preserved in the merged config for forward compatibility; values that map to [NinesConfig](../src/nines/core/config.py) fields (for example `eval.sandbox` → `sandbox_enabled`, `eval.timeout` → `default_timeout`) are applied when loading.
