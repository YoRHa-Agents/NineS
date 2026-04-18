"""NinesConfig: TOML loading, 3-level merge, env var override.

Configuration values are resolved through a 3-level merge (last-writer-wins):
  1. CLI arguments / environment variables     (runtime override)
  2. Project-level  ./nines.toml               (project-specific)
  3. User-level     ~/.config/nines/config.toml (user preferences)
  4. Built-in       src/nines/core/defaults.toml (hardcoded defaults)
"""

from __future__ import annotations

import copy
import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from nines.core.errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)

_DEFAULTS_TOML = Path(__file__).parent / "defaults.toml"

_SECRET_FIELDS = frozenset(
    {
        "github_token",
        "token",
        "collect.github.token",
    }
)

_ENV_PREFIX = "NINES_"

_FIELD_SECTIONS: dict[str, str] = {
    "log_level": "general",
    "log_format": "general",
    "output_dir": "general",
    "data_dir": "general",
    "db_path": "general",
    "no_color": "general",
    "verbose": "general",
    "eval_timeout": "eval",
    "eval_max_retries": "eval",
    "eval_parallel": "eval",
    "default_scorer": "eval",
    "default_timeout": "eval",
    "parallel_workers": "eval",
    "sandbox_enabled": "eval",
    "github_token": "collect.github",
    "arxiv_max_results": "collect.arxiv",
    "collection_interval": "collect.cache",
    "max_file_size": "analyze",
    "supported_languages": "analyze",
    "target_languages": "analyze",
    "convergence_threshold": "iteration.convergence",
    "max_iterations": "iteration",
    "max_rounds": "iteration",
    "baseline_dir": "general",
    "sandbox_timeout": "sandbox",
    "sandbox_max_concurrent": "sandbox",
    "sandbox_use_venv": "sandbox",
}

_ENV_MAP: dict[str, str] = {
    "NINES_LOG_LEVEL": "log_level",
    "NINES_LOG_FORMAT": "log_format",
    "NINES_OUTPUT_DIR": "output_dir",
    "NINES_DATA_DIR": "data_dir",
    "NINES_DB_PATH": "db_path",
    "NINES_NO_COLOR": "no_color",
    "NINES_VERBOSE": "verbose",
    "NINES_EVAL_TIMEOUT": "eval_timeout",
    "NINES_EVAL_MAX_RETRIES": "eval_max_retries",
    "NINES_EVAL_PARALLEL": "eval_parallel",
    "NINES_DEFAULT_SCORER": "default_scorer",
    "NINES_DEFAULT_TIMEOUT": "default_timeout",
    "NINES_PARALLEL_WORKERS": "parallel_workers",
    "NINES_SANDBOX_ENABLED": "sandbox_enabled",
    "NINES_GITHUB_TOKEN": "github_token",
    "NINES_COLLECT_GITHUB_TOKEN": "github_token",
    "NINES_ARXIV_MAX_RESULTS": "arxiv_max_results",
    "NINES_COLLECTION_INTERVAL": "collection_interval",
    "NINES_MAX_FILE_SIZE": "max_file_size",
    "NINES_SUPPORTED_LANGUAGES": "supported_languages",
    "NINES_TARGET_LANGUAGES": "target_languages",
    "NINES_CONVERGENCE_THRESHOLD": "convergence_threshold",
    "NINES_MAX_ITERATIONS": "max_iterations",
    "NINES_MAX_ROUNDS": "max_rounds",
    "NINES_BASELINE_DIR": "baseline_dir",
    "NINES_SANDBOX_TIMEOUT": "sandbox_timeout",
    "NINES_SANDBOX_MAX_CONCURRENT": "sandbox_max_concurrent",
    "NINES_SANDBOX_USE_VENV": "sandbox_use_venv",
}


@dataclass
class NinesConfig:
    """Central configuration object for the NineS framework.

    Fields map to TOML sections as defined in architecture.md §4.2.
    Secret fields (tokens) are masked in __repr__.
    """

    # General
    log_level: str = "INFO"
    log_format: str = "structured"
    output_dir: str = "./reports"
    data_dir: str = "./data"
    db_path: str = "./data/nines.db"
    no_color: bool = False
    verbose: bool = False

    # Eval
    eval_timeout: int = 300
    eval_max_retries: int = 3
    eval_parallel: int = 4
    default_scorer: str = "composite"
    default_timeout: int = 120
    parallel_workers: int = 1
    sandbox_enabled: bool = True

    # Collector
    github_token: str = ""
    arxiv_max_results: int = 100
    collection_interval: int = 3600

    # Analyzer
    max_file_size: int = 1_000_000
    supported_languages: list[str] = field(default_factory=lambda: ["python"])
    target_languages: list[str] = field(default_factory=lambda: ["python"])

    # Iteration
    convergence_threshold: float = 0.05
    max_iterations: int = 10
    max_rounds: int = 10
    baseline_dir: str = "data/baselines"

    # Sandbox
    sandbox_timeout: int = 60
    sandbox_max_concurrent: int = 4
    sandbox_use_venv: bool = True

    # Raw TOML dict for sections not mapped to dataclass fields
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __repr__(self) -> str:
        """Return string representation."""
        parts = [f"{type(self).__name__}("]
        for f in fields(self):
            if f.name.startswith("_"):
                continue
            val = getattr(self, f.name)
            if f.name in _SECRET_FIELDS and val:
                val = "***"
            parts.append(f"  {f.name}={val!r},")
        parts.append(")")
        return "\n".join(parts)

    def validate(self) -> None:
        """Validate config values. Raises ConfigValidationError on invalid."""
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            raise ConfigValidationError(
                f"Invalid log_level '{self.log_level}', "
                f"expected one of: {', '.join(sorted(valid_log_levels))}",
                details={"field": "general.log_level"},
            )

        valid_log_formats = {"structured", "human"}
        if self.log_format not in valid_log_formats:
            raise ConfigValidationError(
                f"Invalid log_format '{self.log_format}', "
                f"expected one of: {', '.join(sorted(valid_log_formats))}",
                details={"field": "general.log_format"},
            )

        valid_scorers = {"exact", "fuzzy", "rubric", "composite"}
        if self.default_scorer not in valid_scorers:
            raise ConfigValidationError(
                f"Invalid default_scorer '{self.default_scorer}', "
                f"expected one of: {', '.join(sorted(valid_scorers))}",
                details={"field": "eval.default_scorer"},
            )

        _check_positive_int(self.eval_timeout, "eval.default_timeout")
        _check_positive_int(self.eval_max_retries, "eval.eval_max_retries")
        _check_positive_int(self.eval_parallel, "eval.eval_parallel")
        _check_positive_int(self.default_timeout, "eval.default_timeout")
        _check_positive_int(self.parallel_workers, "eval.parallel_workers")
        _check_positive_int(self.arxiv_max_results, "collect.arxiv.max_results_per_query")
        _check_positive_int(self.collection_interval, "collect.cache.ttl_seconds")
        _check_positive_int(self.max_file_size, "analyze.max_file_size_kb")
        _check_positive_int(self.max_iterations, "iteration.max_rounds")
        _check_positive_int(self.sandbox_timeout, "sandbox.default_timeout")
        _check_positive_int(self.sandbox_max_concurrent, "sandbox.pool_size")

        if not (0.0 <= self.convergence_threshold <= 1.0):
            raise ConfigValidationError(
                f"convergence_threshold={self.convergence_threshold} out of range [0.0, 1.0]",
                details={"field": "iteration.convergence.variance_threshold"},
            )

        if not isinstance(self.supported_languages, list):
            type_name = type(self.supported_languages).__name__
            raise ConfigValidationError(
                f"supported_languages must be a list, got {type_name}",
                details={"field": "analyze.target_languages"},
            )

        if not isinstance(self.no_color, bool):
            raise ConfigValidationError(
                f"no_color must be a bool, got {type(self.no_color).__name__}",
                details={"field": "general.no_color"},
            )

        if not isinstance(self.sandbox_use_venv, bool):
            raise ConfigValidationError(
                f"sandbox_use_venv must be a bool, got {type(self.sandbox_use_venv).__name__}",
                details={"field": "sandbox.backend"},
            )

    def to_toml(self) -> str:
        """Serialize configuration back to TOML string."""
        try:
            import tomli_w
        except ImportError:
            return _manual_to_toml(self)

        data = _config_to_nested_dict(self)
        return tomli_w.dumps(data)

    def get_raw_section(self, section: str) -> dict[str, Any]:
        """Access the full raw TOML dict for a section (e.g. 'eval.matrix')."""
        parts = section.split(".")
        node = self._raw
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part, {})
            else:
                return {}
        return node if isinstance(node, dict) else {}


def _check_positive_int(value: int, field_name: str) -> None:
    """Check positive int."""
    if not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(
            f"{field_name}={value} must be a positive integer",
            details={"field": field_name},
        )


def load(path: str | None = None) -> NinesConfig:
    """Load config with 3-level merge.

    Search order (highest priority first):
      1. Explicit path argument
      2. ./nines.toml  (project-level)
      3. ~/.config/nines/config.toml  (user-level)
      4. Built-in defaults (src/nines/core/defaults.toml)

    After file merges, environment variables are applied as overrides.
    """
    base = _load_defaults()

    user_config_path = Path.home() / ".config" / "nines" / "config.toml"
    if user_config_path.is_file():
        user_data = _parse_toml_file(user_config_path)
        base = merge(base, user_data)

    project_config_path = Path.cwd() / "nines.toml"
    if project_config_path.is_file():
        project_data = _parse_toml_file(project_config_path)
        base = merge(base, project_data)

    if path is not None:
        explicit_path = Path(path)
        if not explicit_path.is_file():
            raise ConfigFileNotFoundError(
                f"Config file not found: {path}",
                details={"hint": "Check the path and ensure the file exists."},
            )
        explicit_data = _parse_toml_file(explicit_path)
        base = merge(base, explicit_data)

    config = _dict_to_config(base)
    config = from_env(config)
    config.validate()
    return config


def _load_defaults() -> dict[str, Any]:
    """Load the built-in defaults.toml."""
    if not _DEFAULTS_TOML.is_file():
        return {}
    return _parse_toml_file(_DEFAULTS_TOML)


def _parse_toml_file(path: Path) -> dict[str, Any]:
    """Parse a TOML file, raising ConfigParseError on syntax errors."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigParseError(
            f"Failed to parse TOML file: {path}",
            details={"location": str(path), "hint": "Check TOML syntax."},
            cause=e,
        ) from e
    except OSError as e:
        raise ConfigFileNotFoundError(
            f"Cannot read config file: {path}",
            details={"location": str(path)},
            cause=e,
        ) from e


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two config dicts. Override values win for leaf keys."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def from_env(config: NinesConfig | None = None) -> NinesConfig:
    """Override config fields with NINES_* environment variables.

    Env var naming convention: NINES_<SECTION>_<KEY> (uppercase).
    """
    if config is None:
        config = NinesConfig()

    field_types = {f.name: f.type for f in fields(config) if not f.name.startswith("_")}

    for env_key, field_name in _ENV_MAP.items():
        env_val = os.environ.get(env_key)
        if env_val is None:
            continue
        if field_name not in field_types:
            continue

        converted = _convert_env_value(env_val, field_name, field_types[field_name])
        setattr(config, field_name, converted)

    return config


_BOOL_FIELDS: frozenset[str] = frozenset(
    f.name
    for f in fields(NinesConfig)
    if f.type in ("bool",) or (not f.name.startswith("_") and isinstance(f.default, bool))
)

_INT_FIELDS: frozenset[str] = frozenset(
    f.name for f in fields(NinesConfig) if f.type == "int" and not f.name.startswith("_")
)

_FLOAT_FIELDS: frozenset[str] = frozenset(
    f.name for f in fields(NinesConfig) if f.type == "float" and not f.name.startswith("_")
)

_LIST_FIELDS: frozenset[str] = frozenset(
    f.name for f in fields(NinesConfig) if "list" in str(f.type) and not f.name.startswith("_")
)


def _convert_env_value(raw: str, field_name: str, type_hint: str) -> Any:
    """Convert an env var string to the appropriate Python type."""
    if field_name in _BOOL_FIELDS:
        return raw.lower() in ("true", "1", "yes")

    if field_name in _INT_FIELDS:
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigValidationError(
                f"Environment variable for '{field_name}' must be an integer, got '{raw}'",
                details={"field": field_name},
            ) from exc

    if field_name in _FLOAT_FIELDS:
        try:
            return float(raw)
        except ValueError as exc:
            raise ConfigValidationError(
                f"Environment variable for '{field_name}' must be a float, got '{raw}'",
                details={"field": field_name},
            ) from exc

    if field_name in _LIST_FIELDS:
        return [s.strip() for s in raw.split(",") if s.strip()]

    return raw


def _dict_to_config(data: dict[str, Any]) -> NinesConfig:
    """Build a NinesConfig from a nested TOML dict.

    Maps TOML sections (e.g. [general], [eval], [collect.github]) to
    flat dataclass fields using the _FIELD_SECTIONS mapping in reverse.
    """
    flat: dict[str, Any] = {}

    section_to_fields: dict[str, list[str]] = {}
    for fname, section in _FIELD_SECTIONS.items():
        section_to_fields.setdefault(section, []).append(fname)

    for section, field_names in section_to_fields.items():
        parts = section.split(".")
        node = data
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part, {})
            else:
                node = {}
                break

        if isinstance(node, dict):
            for fname in field_names:
                _try_extract_field(node, fname, flat)

    config = NinesConfig(**{k: v for k, v in flat.items() if k in _get_field_names()})
    config._raw = copy.deepcopy(data)
    return config


def _try_extract_field(section_data: dict[str, Any], field_name: str, flat: dict[str, Any]) -> None:
    """Try multiple key variants to extract a field from section data."""
    # Short TOML keys (e.g. ``timeout``) must win over merged defaults that also
    # carry the canonical key (e.g. ``default_timeout`` from defaults.toml).
    priority_alias: dict[str, str] = {
        "default_timeout": "timeout",
    }
    alias_key = priority_alias.get(field_name)
    if alias_key and alias_key in section_data:
        flat[field_name] = section_data[alias_key]
        return

    if field_name in section_data:
        flat[field_name] = section_data[field_name]
        return

    aliases: dict[str, list[str]] = {
        "eval_timeout": ["default_timeout"],
        "eval_max_retries": ["max_retries"],
        "eval_parallel": ["parallel_workers"],
        "sandbox_enabled": ["sandbox"],
        "default_timeout": ["timeout"],
        "github_token": ["token"],
        "arxiv_max_results": ["max_results", "max_results_per_query"],
        "collection_interval": ["ttl_seconds"],
        "max_file_size": ["max_file_size_kb"],
        "supported_languages": ["target_languages"],
        "target_languages": ["target_languages"],
        "max_iterations": ["max_rounds"],
        "max_rounds": ["max_rounds"],
        "convergence_threshold": ["variance_threshold"],
        "sandbox_timeout": ["default_timeout"],
        "sandbox_max_concurrent": ["pool_size"],
        "sandbox_use_venv": ["backend"],
    }

    for alias in aliases.get(field_name, []):
        if alias in section_data:
            val = section_data[alias]
            if field_name == "sandbox_use_venv" and isinstance(val, str):
                flat[field_name] = val == "venv"
            elif field_name == "max_file_size" and isinstance(val, int):
                flat[field_name] = val * 1000
            else:
                flat[field_name] = val
            return


def _get_field_names() -> set[str]:
    """Return set of NinesConfig dataclass field names."""
    return {f.name for f in fields(NinesConfig) if not f.name.startswith("_")}


def _config_to_nested_dict(config: NinesConfig) -> dict[str, Any]:
    """Convert a NinesConfig to a nested dict matching TOML structure."""
    data: dict[str, Any] = {}

    section_map: dict[str, dict[str, str]] = {
        "general": {
            "log_level": "log_level",
            "log_format": "log_format",
            "output_dir": "output_dir",
            "data_dir": "data_dir",
            "db_path": "db_path",
            "no_color": "no_color",
            "verbose": "verbose",
            "baseline_dir": "baseline_dir",
        },
        "eval": {
            "default_scorer": "default_scorer",
            "default_timeout": "default_timeout",
            "parallel_workers": "parallel_workers",
            "sandbox_enabled": "sandbox_enabled",
            "eval_timeout": "eval_timeout",
            "eval_max_retries": "eval_max_retries",
            "eval_parallel": "eval_parallel",
        },
        "collect": {},
        "collect.github": {
            "token": "github_token",
        },
        "collect.arxiv": {
            "max_results_per_query": "arxiv_max_results",
        },
        "collect.cache": {
            "ttl_seconds": "collection_interval",
        },
        "analyze": {
            "target_languages": "target_languages",
            "max_file_size_kb": "max_file_size",
            "supported_languages": "supported_languages",
        },
        "iteration": {
            "max_rounds": "max_rounds",
            "max_iterations": "max_iterations",
        },
        "iteration.convergence": {
            "variance_threshold": "convergence_threshold",
        },
        "sandbox": {
            "default_timeout": "sandbox_timeout",
            "pool_size": "sandbox_max_concurrent",
        },
    }

    for section_path, mapping in section_map.items():
        if not mapping:
            continue
        parts = section_path.split(".")
        node = data
        for part in parts:
            node = node.setdefault(part, {})
        for toml_key, config_field in mapping.items():
            node[toml_key] = getattr(config, config_field)

    return data


def _manual_to_toml(config: NinesConfig) -> str:
    """Fallback TOML serializer when tomli_w is unavailable."""
    lines: list[str] = []
    data = _config_to_nested_dict(config)

    def _write_section(d: dict[str, Any], prefix: str = "") -> None:
        """Write section."""
        scalars = {k: v for k, v in d.items() if not isinstance(v, dict)}
        tables = {k: v for k, v in d.items() if isinstance(v, dict)}

        if scalars and prefix:
            lines.append(f"[{prefix}]")
        for key, val in scalars.items():
            lines.append(f"{key} = {_toml_value(val)}")
        if scalars:
            lines.append("")

        for key, subtable in tables.items():
            sub_prefix = f"{prefix}.{key}" if prefix else key
            _write_section(subtable, sub_prefix)

    _write_section(data)
    return "\n".join(lines)


def _toml_value(val: Any) -> str:
    """Format a Python value as a TOML value string."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(val)
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, list):
        items = ", ".join(_toml_value(v) for v in val)
        return f"[{items}]"
    return f'"{val}"'
