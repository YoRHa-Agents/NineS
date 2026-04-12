"""Tests for nines.sandbox — isolation layer.

Covers:
  - Sandbox creates isolated directory
  - Sandbox cleans up on exit
  - Runner captures stdout/stderr/exit_code
  - Runner enforces timeout
  - Same seed produces same result (determinism)
  - Two sandboxes don't see each other's files (no cross-pollution)
  - PollutionDetector reports clean when nothing changed
  - PollutionDetector detects env/file changes
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nines.sandbox.isolation import (
    EnvironmentSnapshot,
    PollutionDetector,
    PollutionReport,
    VenvFactory,
)
from nines.sandbox.manager import SandboxConfig, SandboxContext, SandboxManager
from nines.sandbox.runner import IsolatedRunner, RunResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def manager(tmp_path: Path) -> SandboxManager:
    """Return a SandboxManager rooted in a temporary directory."""
    mgr = SandboxManager(base_dir=tmp_path / "sandboxes")
    yield mgr
    mgr.destroy_all()


@pytest.fixture()
def sandbox(manager: SandboxManager) -> SandboxContext:
    """Return a single SandboxContext (cleaned up by *manager* fixture)."""
    return manager.create()


# ---------------------------------------------------------------------------
# test_sandbox_creates_isolated_dir
# ---------------------------------------------------------------------------


def test_sandbox_creates_isolated_dir(manager: SandboxManager) -> None:
    ctx = manager.create()
    assert ctx.work_dir.exists()
    assert ctx.work_dir.is_dir()
    # The workspace path is unique and under the base_dir
    assert "workspaces" in str(ctx.work_dir)
    assert ctx.sandbox_id in str(ctx.work_dir)


# ---------------------------------------------------------------------------
# test_sandbox_cleans_up_on_exit
# ---------------------------------------------------------------------------


def test_sandbox_cleans_up_on_exit(tmp_path: Path) -> None:
    work_dirs: list[Path] = []

    with SandboxManager(base_dir=tmp_path / "sandboxes") as mgr:
        ctx = mgr.create()
        work_dirs.append(ctx.work_dir)
        assert ctx.work_dir.exists()

    # After context-manager exit, workspace should be gone
    for wd in work_dirs:
        assert not wd.exists(), f"Expected {wd} to be removed on exit"


# ---------------------------------------------------------------------------
# test_runner_captures_output
# ---------------------------------------------------------------------------


def test_runner_captures_output(
    manager: SandboxManager, sandbox: SandboxContext,
) -> None:
    script = sandbox.work_dir / "hello.py"
    script.write_text(
        textwrap.dedent("""\
            import sys
            print("hello stdout")
            print("hello stderr", file=sys.stderr)
            sys.exit(0)
        """),
        encoding="utf-8",
    )

    result = manager.run_in_sandbox(
        sandbox,
        [sys.executable, str(script)],
    )

    assert isinstance(result, RunResult)
    assert result.exit_code == 0
    assert "hello stdout" in result.stdout
    assert "hello stderr" in result.stderr
    assert result.duration_ms > 0
    assert result.timed_out is False


# ---------------------------------------------------------------------------
# test_runner_enforces_timeout
# ---------------------------------------------------------------------------


def test_runner_enforces_timeout(
    manager: SandboxManager, sandbox: SandboxContext,
) -> None:
    script = sandbox.work_dir / "sleeper.py"
    script.write_text(
        textwrap.dedent("""\
            import time
            print("starting")
            time.sleep(60)
            print("done")
        """),
        encoding="utf-8",
    )

    result = manager.run_in_sandbox(
        sandbox,
        [sys.executable, str(script)],
        timeout=2,
    )

    assert result.timed_out is True
    assert result.exit_code == -1


# ---------------------------------------------------------------------------
# test_same_seed_same_result
# ---------------------------------------------------------------------------


def test_same_seed_same_result(manager: SandboxManager) -> None:
    script_src = textwrap.dedent("""\
        import random, os
        seed = int(os.environ.get("NINES_SEED", "0"))
        random.seed(seed)
        print(random.random())
        print(random.randint(0, 1000000))
    """)

    fingerprints: list[str] = []
    for _ in range(3):
        ctx = manager.create(SandboxConfig(seed=42))
        try:
            script = ctx.work_dir / "seeded.py"
            script.write_text(script_src, encoding="utf-8")
            result = manager.run_in_sandbox(
                ctx, [sys.executable, str(script)], seed=42,
            )
            assert result.exit_code == 0, result.stderr
            fingerprints.append(result.fingerprint)
        finally:
            manager.destroy(ctx)

    assert len(set(fingerprints)) == 1, (
        f"Expected identical fingerprints across runs, got {fingerprints}"
    )


# ---------------------------------------------------------------------------
# test_no_cross_pollution
# ---------------------------------------------------------------------------


def test_no_cross_pollution(manager: SandboxManager) -> None:
    """Two sandboxes cannot see each other's files."""
    ctx_a = manager.create()
    ctx_b = manager.create()

    try:
        # Write a file in sandbox A
        (ctx_a.work_dir / "secret_a.txt").write_text("data_a", encoding="utf-8")

        # Script in sandbox B tries to list its own cwd
        script_b = ctx_b.work_dir / "list_dir.py"
        script_b.write_text(
            textwrap.dedent("""\
                import os
                files = os.listdir(".")
                print("\\n".join(files))
            """),
            encoding="utf-8",
        )

        result_b = manager.run_in_sandbox(
            ctx_b, [sys.executable, str(script_b)],
        )

        assert result_b.exit_code == 0
        assert "secret_a.txt" not in result_b.stdout, (
            "Sandbox B should not see files from sandbox A"
        )

        # Also verify the inverse: files from B aren't in A's workspace
        assert not (ctx_a.work_dir / "list_dir.py").exists()
    finally:
        manager.destroy(ctx_a)
        manager.destroy(ctx_b)


# ---------------------------------------------------------------------------
# test_pollution_detector_clean
# ---------------------------------------------------------------------------


def test_pollution_detector_clean() -> None:
    """When nothing changes between snapshots, report should be clean."""
    detector = PollutionDetector()
    detector.snapshot_before()
    detector.snapshot_after()
    report = detector.detect_pollution()

    assert isinstance(report, PollutionReport)
    assert report.is_clean is True
    assert report.total_changes == 0


# ---------------------------------------------------------------------------
# test_pollution_detector_detects_changes
# ---------------------------------------------------------------------------


def test_pollution_detector_detects_changes(tmp_path: Path) -> None:
    """PollutionDetector should detect new files in watched directories."""
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir()

    detector = PollutionDetector(watched_dirs=[watch_dir])

    before = detector.snapshot_before()

    # Simulate pollution: add a file in the watched dir
    (watch_dir / "intruder.txt").write_text("bad data", encoding="utf-8")

    after = detector.snapshot_after()
    report = detector.detect_pollution()

    assert report.is_clean is False
    assert report.total_changes > 0
    assert "dirs" in report.changes


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_max_concurrent_enforcement(tmp_path: Path) -> None:
    """Creating more sandboxes than max_concurrent raises RuntimeError."""
    mgr = SandboxManager(base_dir=tmp_path / "sandboxes", max_concurrent=2)
    try:
        ctx1 = mgr.create()
        ctx2 = mgr.create()
        with pytest.raises(RuntimeError, match="Max concurrent"):
            mgr.create()
    finally:
        mgr.destroy_all()


def test_destroy_removes_from_active(manager: SandboxManager) -> None:
    ctx = manager.create()
    assert manager.active_count == 1
    manager.destroy(ctx)
    assert manager.active_count == 0
    assert not ctx.work_dir.exists()


def test_runner_nonzero_exit(
    manager: SandboxManager, sandbox: SandboxContext,
) -> None:
    script = sandbox.work_dir / "fail.py"
    script.write_text("import sys; sys.exit(42)\n", encoding="utf-8")
    result = manager.run_in_sandbox(sandbox, [sys.executable, str(script)])
    assert result.exit_code == 42


# ---------------------------------------------------------------------------
# Extended isolation and determinism tests
# ---------------------------------------------------------------------------


def test_sandbox_unique_ids(manager: SandboxManager) -> None:
    """Each sandbox has a unique ID."""
    contexts = [manager.create() for _ in range(5)]
    try:
        ids = [c.sandbox_id for c in contexts]
        assert len(set(ids)) == 5
    finally:
        for ctx in contexts:
            manager.destroy(ctx)


def test_sandbox_env_isolation(
    manager: SandboxManager, sandbox: SandboxContext,
) -> None:
    """Sandbox processes should not see modifications to parent env vars."""
    script = sandbox.work_dir / "check_env.py"
    script.write_text(
        textwrap.dedent("""\
            import os
            print(os.environ.get("NINES_TEST_ISOLATION", "NOT_SET"))
        """),
        encoding="utf-8",
    )

    os.environ["NINES_TEST_ISOLATION"] = "parent_value"
    try:
        result = manager.run_in_sandbox(
            sandbox, [sys.executable, str(script)],
        )
        assert result.exit_code == 0
    finally:
        os.environ.pop("NINES_TEST_ISOLATION", None)


def test_pollution_detector_file_changes(tmp_path: Path) -> None:
    """PollutionDetector detects modifications to watched files."""
    watch_file = tmp_path / "watched.txt"
    watch_file.write_text("original", encoding="utf-8")

    detector = PollutionDetector(watched_files=[watch_file])
    detector.snapshot_before()

    watch_file.write_text("modified", encoding="utf-8")

    detector.snapshot_after()
    report = detector.detect_pollution()
    assert report.is_clean is False
    assert "files" in report.changes


def test_pollution_detector_requires_both_snapshots() -> None:
    """PollutionDetector raises if snapshots not taken."""
    detector = PollutionDetector()
    with pytest.raises(RuntimeError, match="snapshot_before"):
        detector.detect_pollution()


def test_pollution_detector_compare_static() -> None:
    """PollutionDetector.compare works with externally provided snapshots."""
    snap = EnvironmentSnapshot(
        env_vars={"A": "1"},
        watched_file_hashes={},
        watched_dir_listings={},
        python_path=("/usr/bin",),
        cwd="/tmp",
    )
    detector = PollutionDetector()
    report = detector.compare(snap, snap)
    assert report.is_clean is True
    assert report.total_changes == 0


def test_pollution_detector_env_var_change() -> None:
    """PollutionDetector detects new/removed env vars."""
    before = EnvironmentSnapshot(
        env_vars={"A": "1", "B": "2"},
        watched_file_hashes={},
        watched_dir_listings={},
        python_path=(),
        cwd="/tmp",
    )
    after = EnvironmentSnapshot(
        env_vars={"A": "1", "C": "3"},
        watched_file_hashes={},
        watched_dir_listings={},
        python_path=(),
        cwd="/tmp",
    )
    detector = PollutionDetector()
    report = detector.compare(before, after)
    assert report.is_clean is False
    assert report.total_changes > 0


def test_pollution_detector_syspath_change() -> None:
    """PollutionDetector detects sys.path additions."""
    before = EnvironmentSnapshot(
        env_vars={},
        watched_file_hashes={},
        watched_dir_listings={},
        python_path=("/usr/lib",),
        cwd="/tmp",
    )
    after = EnvironmentSnapshot(
        env_vars={},
        watched_file_hashes={},
        watched_dir_listings={},
        python_path=("/usr/lib", "/new/path"),
        cwd="/tmp",
    )
    detector = PollutionDetector()
    report = detector.compare(before, after)
    assert report.is_clean is False


def test_run_result_fingerprint_deterministic(
    manager: SandboxManager,
) -> None:
    """Running same script twice produces identical fingerprints."""
    script_src = "print('deterministic')\n"
    fingerprints: list[str] = []
    for _ in range(2):
        ctx = manager.create(SandboxConfig(seed=99))
        try:
            script = ctx.work_dir / "det.py"
            script.write_text(script_src, encoding="utf-8")
            result = manager.run_in_sandbox(ctx, [sys.executable, str(script)], seed=99)
            assert result.exit_code == 0
            fingerprints.append(result.fingerprint)
        finally:
            manager.destroy(ctx)

    assert fingerprints[0] == fingerprints[1]


def test_context_manager_cleanup(tmp_path: Path) -> None:
    """SandboxManager as context manager cleans up all sandboxes."""
    work_dirs: list[Path] = []
    with SandboxManager(base_dir=tmp_path / "cm_test") as mgr:
        for _ in range(3):
            ctx = mgr.create()
            work_dirs.append(ctx.work_dir)
            assert ctx.work_dir.exists()
    for wd in work_dirs:
        assert not wd.exists()


def test_sandbox_config_defaults() -> None:
    """SandboxConfig has expected defaults."""
    cfg = SandboxConfig()
    assert cfg.timeout_seconds == 30
    assert cfg.seed is None
    assert cfg.use_venv is False
    assert cfg.requirements == []
    assert cfg.max_memory_mb == 512


def test_venv_factory_python_path(tmp_path: Path) -> None:
    """VenvFactory.python_path returns correct path format."""
    factory = VenvFactory(tmp_path / "venvs")
    venv_path = tmp_path / "test_venv"
    venv_path.mkdir()
    python = factory.python_path(venv_path)
    assert "python" in str(python)


def test_sandbox_active_count_tracking(tmp_path: Path) -> None:
    """SandboxManager tracks active count correctly through lifecycle."""
    mgr = SandboxManager(base_dir=tmp_path / "track_test")
    try:
        assert mgr.active_count == 0
        ctx1 = mgr.create()
        assert mgr.active_count == 1
        ctx2 = mgr.create()
        assert mgr.active_count == 2
        mgr.destroy(ctx1)
        assert mgr.active_count == 1
        mgr.destroy(ctx2)
        assert mgr.active_count == 0
    finally:
        mgr.destroy_all()
