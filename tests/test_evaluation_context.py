"""Tests for ``nines.iteration.context.EvaluationContext`` (C01 Phase 1).

Covers:
- Path validation in :meth:`from_cli` (missing project_root / src_dir raise).
- Fingerprint stability across repeated calls and distinctness across paths.
- Relative-path resolution against ``project_root``.
- ``to_dict`` round-trip.
- ``requires_writable`` defaults to ``False``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.core.errors import ConfigError  # noqa: E402
from nines.iteration.context import EvaluationContext  # noqa: E402


def _make_layout(root: Path) -> tuple[Path, Path, Path]:
    """Create a minimal project tree under ``root`` and return the paths."""
    src = root / "src"
    src.mkdir(parents=True)
    (src / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_x(): pass\n", encoding="utf-8")
    return root, src, tests


def test_context_construction_validates_paths(tmp_path: Path) -> None:
    """Missing ``project_root`` / non-existent ``src_dir`` must raise ConfigError."""
    # Empty project_root → ConfigError
    with pytest.raises(ConfigError):
        EvaluationContext.from_cli(project_root="", src_dir="src")

    # Empty src_dir → ConfigError
    with pytest.raises(ConfigError):
        EvaluationContext.from_cli(project_root=str(tmp_path), src_dir="")

    # Non-existent project_root → ConfigError
    with pytest.raises(ConfigError):
        EvaluationContext.from_cli(
            project_root=str(tmp_path / "no_such_dir"),
            src_dir="src",
        )

    # Existing project_root + non-existent src_dir → ConfigError
    project_root, _, _ = _make_layout(tmp_path)
    with pytest.raises(ConfigError):
        EvaluationContext.from_cli(
            project_root=str(project_root),
            src_dir="missing_subdir",
        )


def test_context_fingerprint_stable(tmp_path: Path) -> None:
    """Two contexts built from the same paths produce identical fingerprints."""
    project_root, _, _ = _make_layout(tmp_path)
    ctx1 = EvaluationContext.from_cli(project_root=str(project_root), src_dir="src")
    ctx2 = EvaluationContext.from_cli(project_root=str(project_root), src_dir="src")

    fp1 = ctx1.fingerprint()
    fp2 = ctx2.fingerprint()

    assert fp1 == fp2, f"fingerprint not stable: {fp1!r} vs {fp2!r}"
    # Repeated invocations on the same context must also be stable.
    assert ctx1.fingerprint() == fp1
    # 8-char lowercase hex per the C02-aligned design.
    assert len(fp1) == 8
    assert all(c in "0123456789abcdef" for c in fp1)


def test_context_fingerprint_distinct(tmp_path: Path) -> None:
    """Different ``src_dir`` values produce distinct fingerprints."""
    project_root, _, _ = _make_layout(tmp_path)
    other_src = tmp_path / "other_src"
    other_src.mkdir()
    (other_src / "lib.py").write_text("", encoding="utf-8")

    ctx_a = EvaluationContext.from_cli(project_root=str(project_root), src_dir="src")
    ctx_b = EvaluationContext.from_cli(
        project_root=str(project_root),
        src_dir="other_src",
    )

    assert ctx_a.fingerprint() != ctx_b.fingerprint(), (
        "different src_dirs collapsed to the same fingerprint"
    )


def test_context_from_cli_resolves_relative_paths(tmp_path: Path) -> None:
    """Relative paths are resolved against ``project_root``."""
    project_root, src, tests = _make_layout(tmp_path)

    # --src-dir given as a relative path → resolved under project_root
    ctx = EvaluationContext.from_cli(
        project_root=str(project_root),
        src_dir="src",
        test_dir="tests",
    )
    assert ctx.src_dir == src.resolve()
    assert ctx.test_dir is not None
    assert ctx.test_dir == tests.resolve()
    # An absolute --src-dir must be honored as-is.
    abs_ctx = EvaluationContext.from_cli(
        project_root=str(project_root),
        src_dir=str(src),
    )
    assert abs_ctx.src_dir == src.resolve()


def test_context_to_dict_round_trips(tmp_path: Path) -> None:
    """``from_dict(to_dict(...))`` preserves all fields."""
    project_root, src, tests = _make_layout(tmp_path)
    ctx = EvaluationContext.from_cli(
        project_root=str(project_root),
        src_dir="src",
        test_dir="tests",
        metadata={"git_rev": "deadbeef"},
    )
    payload = ctx.to_dict()

    assert payload["project_root"] == str(project_root.resolve())
    assert payload["src_dir"] == str(src.resolve())
    assert payload["test_dir"] == str(tests.resolve())
    assert payload["metadata"] == {"git_rev": "deadbeef"}
    assert payload["fingerprint"] == ctx.fingerprint()

    rebuilt = EvaluationContext.from_dict(payload)
    assert rebuilt.project_root == ctx.project_root
    assert rebuilt.src_dir == ctx.src_dir
    assert rebuilt.test_dir == ctx.test_dir
    assert rebuilt.metadata == ctx.metadata
    assert rebuilt.fingerprint() == ctx.fingerprint()


def test_context_requires_writable_is_false(tmp_path: Path) -> None:
    """The v3.2.0 baseline behaviour is read-only."""
    project_root, _, _ = _make_layout(tmp_path)
    ctx = EvaluationContext.from_cli(project_root=str(project_root), src_dir="src")
    assert ctx.requires_writable() is False
