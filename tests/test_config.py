"""Tests for the NineS configuration system.

Covers: loading, merging, env overrides, validation, search order.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from nines.core.config import NinesConfig, from_env, load, merge
from nines.core.errors import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Return a temp directory for config files."""
    return tmp_path


@pytest.fixture
def write_toml(tmp_config_dir: Path):
    """Helper to write a TOML string to a temp file and return its path."""

    def _write(content: str, name: str = "test.toml") -> Path:
        p = tmp_config_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content))
        return p

    return _write


@pytest.fixture(autouse=True)
def _clean_env():
    """Remove all NINES_* env vars before and after each test."""
    nines_keys = [k for k in os.environ if k.startswith("NINES_")]
    for k in nines_keys:
        del os.environ[k]
    yield
    nines_keys = [k for k in os.environ if k.startswith("NINES_")]
    for k in nines_keys:
        del os.environ[k]


# ---------------------------------------------------------------------------
# test_default_config_valid
# ---------------------------------------------------------------------------


class TestDefaultConfigValid:
    """Built-in defaults must produce a valid NinesConfig."""

    def test_defaults_load_without_error(self):
        cfg = NinesConfig()
        cfg.validate()

    def test_default_log_level(self):
        cfg = NinesConfig()
        assert cfg.log_level == "INFO"

    def test_default_output_dir(self):
        cfg = NinesConfig()
        assert cfg.output_dir == "./reports"

    def test_default_data_dir(self):
        cfg = NinesConfig()
        assert cfg.data_dir == "./data"

    def test_default_eval_timeout(self):
        cfg = NinesConfig()
        assert cfg.eval_timeout == 300

    def test_default_eval_parallel(self):
        cfg = NinesConfig()
        assert cfg.eval_parallel == 4

    def test_default_github_token_empty(self):
        cfg = NinesConfig()
        assert cfg.github_token == ""

    def test_default_supported_languages(self):
        cfg = NinesConfig()
        assert cfg.supported_languages == ["python"]

    def test_default_convergence_threshold(self):
        cfg = NinesConfig()
        assert cfg.convergence_threshold == 0.05

    def test_default_sandbox_use_venv(self):
        cfg = NinesConfig()
        assert cfg.sandbox_use_venv is True

    def test_secret_masking_in_repr(self):
        cfg = NinesConfig(github_token="ghp_secrettoken123")
        r = repr(cfg)
        assert "ghp_secrettoken123" not in r
        assert "***" in r


# ---------------------------------------------------------------------------
# test_load_from_file
# ---------------------------------------------------------------------------


class TestLoadFromFile:
    """Loading config from an explicit TOML file."""

    def test_load_explicit_path(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "DEBUG"
            output_dir = "/tmp/nines-out"
        """)
        cfg = load(str(p))
        assert cfg.log_level == "DEBUG"
        assert cfg.output_dir == "/tmp/nines-out"

    def test_load_overrides_defaults(self, write_toml):
        p = write_toml("""\
            [eval]
            default_timeout = 999
        """)
        cfg = load(str(p))
        assert cfg.default_timeout == 999
        assert cfg.log_level == "INFO"

    def test_load_missing_file_raises(self):
        with pytest.raises(ConfigFileNotFoundError):
            load("/nonexistent/path/config.toml")

    def test_load_invalid_toml_raises(self, write_toml):
        p = write_toml("this is not valid [[ toml")
        with pytest.raises(ConfigParseError):
            load(str(p))

    def test_load_preserves_raw_sections(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "WARNING"

            [eval.matrix]
            max_cells = 500
            sampling_strategy = "latin_square"
        """)
        cfg = load(str(p))
        matrix = cfg.get_raw_section("eval.matrix")
        assert matrix.get("max_cells") == 500
        assert matrix.get("sampling_strategy") == "latin_square"

    def test_load_github_token(self, write_toml):
        p = write_toml("""\
            [collect.github]
            token = "ghp_test123"
        """)
        cfg = load(str(p))
        assert cfg.github_token == "ghp_test123"

    def test_load_sandbox_settings(self, write_toml):
        p = write_toml("""\
            [sandbox]
            default_timeout = 600
            pool_size = 8
        """)
        cfg = load(str(p))
        assert cfg.sandbox_timeout == 600
        assert cfg.sandbox_max_concurrent == 8

    def test_load_eval_sandbox_and_timeout_aliases(self, write_toml):
        p = write_toml("""\
            [eval]
            sandbox = true
            timeout = 60
        """)
        cfg = load(str(p))
        assert cfg.sandbox_enabled is True
        assert cfg.default_timeout == 60

    def test_samples_config_file_loads(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        path = repo_root / "samples" / "config" / "nines.toml"
        cfg = load(str(path))
        assert cfg.default_scorer == "composite"
        assert cfg.sandbox_enabled is True
        assert cfg.default_timeout == 60
        assert cfg.arxiv_max_results == 50


# ---------------------------------------------------------------------------
# test_env_override
# ---------------------------------------------------------------------------


class TestEnvOverride:
    """Environment variables override file config values."""

    def test_nines_log_level(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "INFO"
        """)
        os.environ["NINES_LOG_LEVEL"] = "DEBUG"
        cfg = load(str(p))
        assert cfg.log_level == "DEBUG"

    def test_nines_github_token(self):
        os.environ["NINES_GITHUB_TOKEN"] = "ghp_from_env"
        cfg = from_env(NinesConfig())
        assert cfg.github_token == "ghp_from_env"

    def test_nines_collect_github_token(self):
        os.environ["NINES_COLLECT_GITHUB_TOKEN"] = "ghp_alt_env"
        cfg = from_env(NinesConfig())
        assert cfg.github_token == "ghp_alt_env"

    def test_nines_eval_timeout_int_conversion(self):
        os.environ["NINES_EVAL_TIMEOUT"] = "600"
        cfg = from_env(NinesConfig())
        assert cfg.eval_timeout == 600
        assert isinstance(cfg.eval_timeout, int)

    def test_nines_convergence_threshold_float_conversion(self):
        os.environ["NINES_CONVERGENCE_THRESHOLD"] = "0.10"
        cfg = from_env(NinesConfig())
        assert cfg.convergence_threshold == 0.10

    def test_nines_sandbox_use_venv_bool_conversion(self):
        os.environ["NINES_SANDBOX_USE_VENV"] = "false"
        cfg = from_env(NinesConfig())
        assert cfg.sandbox_use_venv is False

    def test_nines_supported_languages_list_conversion(self):
        os.environ["NINES_SUPPORTED_LANGUAGES"] = "python,javascript,rust"
        cfg = from_env(NinesConfig())
        assert cfg.supported_languages == ["python", "javascript", "rust"]

    def test_env_invalid_int_raises(self):
        os.environ["NINES_EVAL_TIMEOUT"] = "not_a_number"
        with pytest.raises(ConfigValidationError):
            from_env(NinesConfig())

    def test_env_overrides_file_config(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "ERROR"
        """)
        os.environ["NINES_LOG_LEVEL"] = "WARNING"
        cfg = load(str(p))
        assert cfg.log_level == "WARNING"

    def test_nines_no_color(self):
        os.environ["NINES_NO_COLOR"] = "true"
        cfg = from_env(NinesConfig())
        assert cfg.no_color is True

    def test_nines_output_dir(self):
        os.environ["NINES_OUTPUT_DIR"] = "/custom/output"
        cfg = from_env(NinesConfig())
        assert cfg.output_dir == "/custom/output"


# ---------------------------------------------------------------------------
# test_merge_configs
# ---------------------------------------------------------------------------


class TestMergeConfigs:
    """Deep merge of config dictionaries."""

    def test_merge_flat(self):
        base = {"general": {"log_level": "INFO", "output_dir": "./reports"}}
        override = {"general": {"log_level": "DEBUG"}}
        result = merge(base, override)
        assert result["general"]["log_level"] == "DEBUG"
        assert result["general"]["output_dir"] == "./reports"

    def test_merge_nested(self):
        base = {"eval": {"scorers": {"fuzzy": {"threshold": 0.8}}}}
        override = {"eval": {"scorers": {"fuzzy": {"threshold": 0.9, "algo": "edit"}}}}
        result = merge(base, override)
        assert result["eval"]["scorers"]["fuzzy"]["threshold"] == 0.9
        assert result["eval"]["scorers"]["fuzzy"]["algo"] == "edit"

    def test_merge_adds_new_keys(self):
        base = {"general": {"log_level": "INFO"}}
        override = {"eval": {"timeout": 60}}
        result = merge(base, override)
        assert result["general"]["log_level"] == "INFO"
        assert result["eval"]["timeout"] == 60

    def test_merge_override_wins_for_scalars(self):
        base = {"x": 1}
        override = {"x": 2}
        result = merge(base, override)
        assert result["x"] == 2

    def test_merge_does_not_mutate_base(self):
        base = {"general": {"log_level": "INFO"}}
        override = {"general": {"log_level": "DEBUG"}}
        merge(base, override)
        assert base["general"]["log_level"] == "INFO"

    def test_merge_list_replacement(self):
        base = {"langs": ["python"]}
        override = {"langs": ["python", "rust"]}
        result = merge(base, override)
        assert result["langs"] == ["python", "rust"]

    def test_three_level_merge(self):
        defaults = {"general": {"log_level": "INFO", "verbose": False}}
        user = {"general": {"log_level": "WARNING"}}
        project = {"general": {"verbose": True}}
        step1 = merge(defaults, user)
        step2 = merge(step1, project)
        assert step2["general"]["log_level"] == "WARNING"
        assert step2["general"]["verbose"] is True


# ---------------------------------------------------------------------------
# test_invalid_config_raises
# ---------------------------------------------------------------------------


class TestInvalidConfigRaises:
    """Invalid configuration values must raise ConfigError / subclasses."""

    def test_invalid_log_level(self):
        cfg = NinesConfig(log_level="INVALID")
        with pytest.raises(ConfigValidationError, match="log_level"):
            cfg.validate()

    def test_invalid_log_format(self):
        cfg = NinesConfig(log_format="xml")
        with pytest.raises(ConfigValidationError, match="log_format"):
            cfg.validate()

    def test_invalid_default_scorer(self):
        cfg = NinesConfig(default_scorer="magic")
        with pytest.raises(ConfigValidationError, match="default_scorer"):
            cfg.validate()

    def test_negative_eval_timeout(self):
        cfg = NinesConfig(eval_timeout=-1)
        with pytest.raises(ConfigValidationError):
            cfg.validate()

    def test_zero_eval_parallel(self):
        cfg = NinesConfig(eval_parallel=0)
        with pytest.raises(ConfigValidationError):
            cfg.validate()

    def test_convergence_threshold_out_of_range(self):
        cfg = NinesConfig(convergence_threshold=1.5)
        with pytest.raises(ConfigValidationError, match="convergence_threshold"):
            cfg.validate()

    def test_convergence_threshold_negative(self):
        cfg = NinesConfig(convergence_threshold=-0.1)
        with pytest.raises(ConfigValidationError, match="convergence_threshold"):
            cfg.validate()

    def test_negative_max_iterations(self):
        cfg = NinesConfig(max_iterations=-5)
        with pytest.raises(ConfigValidationError):
            cfg.validate()

    def test_zero_sandbox_timeout(self):
        cfg = NinesConfig(sandbox_timeout=0)
        with pytest.raises(ConfigValidationError):
            cfg.validate()

    def test_invalid_toml_file(self, write_toml):
        p = write_toml("[[broken toml!!! = ")
        with pytest.raises(ConfigParseError):
            load(str(p))

    def test_missing_file_raises_not_found(self):
        with pytest.raises(ConfigFileNotFoundError):
            load("/does/not/exist.toml")

    def test_config_error_hierarchy(self):
        assert issubclass(ConfigValidationError, ConfigError)
        assert issubclass(ConfigParseError, ConfigError)
        assert issubclass(ConfigFileNotFoundError, ConfigError)

    def test_config_error_has_message(self):
        err = ConfigValidationError("bad value", details={"field": "test"})
        assert err.message == "bad value"
        assert err.details["field"] == "test"


# ---------------------------------------------------------------------------
# test_search_order
# ---------------------------------------------------------------------------


class TestSearchOrder:
    """Config search order: explicit > project > user > defaults."""

    def test_explicit_overrides_project(self, tmp_path, monkeypatch):
        project_toml = tmp_path / "project" / "nines.toml"
        project_toml.parent.mkdir(parents=True)
        project_toml.write_text('[general]\nlog_level = "WARNING"\n')

        explicit_toml = tmp_path / "explicit.toml"
        explicit_toml.write_text('[general]\nlog_level = "ERROR"\n')

        monkeypatch.chdir(project_toml.parent)
        cfg = load(str(explicit_toml))
        assert cfg.log_level == "ERROR"

    def test_project_overrides_user(self, tmp_path, monkeypatch):
        user_dir = tmp_path / "home" / ".config" / "nines"
        user_dir.mkdir(parents=True)
        user_config = user_dir / "config.toml"
        user_config.write_text('[general]\nlog_level = "DEBUG"\noutput_dir = "/user/out"\n')

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_toml = project_dir / "nines.toml"
        project_toml.write_text('[general]\nlog_level = "ERROR"\n')

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(project_dir)

        cfg = load()
        assert cfg.log_level == "ERROR"
        assert cfg.output_dir == "/user/out"

    def test_user_overrides_builtin(self, tmp_path, monkeypatch):
        user_dir = tmp_path / "home" / ".config" / "nines"
        user_dir.mkdir(parents=True)
        user_config = user_dir / "config.toml"
        user_config.write_text('[general]\nlog_level = "WARNING"\n')

        work_dir = tmp_path / "work"
        work_dir.mkdir()

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(work_dir)

        cfg = load()
        assert cfg.log_level == "WARNING"

    def test_builtin_defaults_used_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
        monkeypatch.chdir(tmp_path)

        cfg = load()
        assert cfg.log_level == "INFO"
        assert cfg.output_dir == "./reports"

    def test_env_overrides_all_file_sources(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        project_toml = project_dir / "nines.toml"
        project_toml.write_text('[general]\nlog_level = "ERROR"\n')

        monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
        monkeypatch.chdir(project_dir)
        os.environ["NINES_LOG_LEVEL"] = "CRITICAL"

        cfg = load()
        assert cfg.log_level == "CRITICAL"


# ---------------------------------------------------------------------------
# test_to_toml (serialization)
# ---------------------------------------------------------------------------


class TestToToml:
    """Config can be serialized back to TOML."""

    def test_roundtrip_basic(self):
        cfg = NinesConfig()
        toml_str = cfg.to_toml()
        assert "log_level" in toml_str
        assert "INFO" in toml_str

    def test_roundtrip_custom_values(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "DEBUG"
            verbose = true
        """)
        cfg = load(str(p))
        toml_str = cfg.to_toml()
        assert "DEBUG" in toml_str


# ---------------------------------------------------------------------------
# Additional config tests for coverage
# ---------------------------------------------------------------------------


class TestConfigEdgeCases:
    """Cover uncovered config code paths."""

    def test_validate_supported_languages_not_list(self):
        cfg = NinesConfig()
        cfg.supported_languages = "python"  # type: ignore[assignment]
        with pytest.raises(ConfigValidationError, match="supported_languages"):
            cfg.validate()

    def test_validate_no_color_not_bool(self):
        cfg = NinesConfig()
        cfg.no_color = "yes"  # type: ignore[assignment]
        with pytest.raises(ConfigValidationError, match="no_color"):
            cfg.validate()

    def test_validate_sandbox_use_venv_not_bool(self):
        cfg = NinesConfig()
        cfg.sandbox_use_venv = "true"  # type: ignore[assignment]
        with pytest.raises(ConfigValidationError, match="sandbox_use_venv"):
            cfg.validate()

    def test_get_raw_section_nonexistent(self):
        cfg = NinesConfig()
        result = cfg.get_raw_section("nonexistent.section")
        assert result == {}

    def test_get_raw_section_with_data(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "INFO"
            [custom]
            key = "value"
        """)
        cfg = load(str(p))
        custom = cfg.get_raw_section("custom")
        assert custom.get("key") == "value"

    def test_env_float_invalid_raises(self):
        os.environ["NINES_CONVERGENCE_THRESHOLD"] = "not_float"
        with pytest.raises(ConfigValidationError):
            from_env(NinesConfig())

    def test_from_env_none_config_creates_default(self):
        cfg = from_env(None)
        assert isinstance(cfg, NinesConfig)
        assert cfg.log_level == "INFO"

    def test_manual_to_toml_fallback(self):
        from nines.core.config import _manual_to_toml

        cfg = NinesConfig()
        result = _manual_to_toml(cfg)
        assert "log_level" in result
        assert "INFO" in result

    def test_toml_value_types(self):
        from nines.core.config import _toml_value

        assert _toml_value(True) == "true"
        assert _toml_value(False) == "false"
        assert _toml_value(42) == "42"
        assert _toml_value(3.14) == "3.14"
        assert _toml_value("hello") == '"hello"'
        assert _toml_value(["a", "b"]) == '["a", "b"]'
        assert _toml_value(None) == '"None"'

    def test_load_with_sandbox_backend_alias(self, write_toml):
        p = write_toml("""\
            [sandbox]
            backend = "venv"
        """)
        cfg = load(str(p))
        assert cfg.sandbox_use_venv is True

    def test_load_with_sandbox_backend_non_venv(self, write_toml):
        p = write_toml("""\
            [sandbox]
            backend = "docker"
        """)
        cfg = load(str(p))
        assert cfg.sandbox_use_venv is False

    def test_load_with_max_file_size_kb_alias(self, write_toml):
        p = write_toml("""\
            [analyze]
            max_file_size_kb = 500
        """)
        cfg = load(str(p))
        assert cfg.max_file_size == 500_000

    def test_load_with_convergence_variance_alias(self, write_toml):
        p = write_toml("""\
            [iteration.convergence]
            variance_threshold = 0.03
        """)
        cfg = load(str(p))
        assert cfg.convergence_threshold == 0.03

    def test_dict_to_config_non_dict_node(self, write_toml):
        p = write_toml("""\
            [general]
            log_level = "INFO"
        """)
        cfg = load(str(p))
        assert cfg.log_level == "INFO"

    def test_check_positive_int_zero(self):
        from nines.core.config import _check_positive_int

        with pytest.raises(ConfigValidationError):
            _check_positive_int(0, "test_field")

    def test_check_positive_int_negative(self):
        from nines.core.config import _check_positive_int

        with pytest.raises(ConfigValidationError):
            _check_positive_int(-1, "test_field")

    def test_check_positive_int_not_int(self):
        from nines.core.config import _check_positive_int

        with pytest.raises(ConfigValidationError):
            _check_positive_int(3.5, "test_field")  # type: ignore[arg-type]

    def test_repr_no_internal_fields(self):
        cfg = NinesConfig()
        r = repr(cfg)
        assert "_raw" not in r

    def test_validate_boundary_convergence_threshold(self):
        cfg = NinesConfig(convergence_threshold=0.0)
        cfg.validate()
        cfg2 = NinesConfig(convergence_threshold=1.0)
        cfg2.validate()

    def test_env_bool_variants(self):
        for val, expected in [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
        ]:
            os.environ["NINES_NO_COLOR"] = val
            cfg = from_env(NinesConfig())
            assert cfg.no_color is expected

    def test_env_list_with_spaces(self):
        os.environ["NINES_SUPPORTED_LANGUAGES"] = " python , rust , go "
        cfg = from_env(NinesConfig())
        assert cfg.supported_languages == ["python", "rust", "go"]
