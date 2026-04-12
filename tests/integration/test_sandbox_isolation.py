"""Integration test: sandbox isolation verification.

Proves:
1. No system pollution — host env unchanged after sandbox execution
2. No cross-pollution — sandboxes cannot see each other's files
3. Deterministic re-test — same seed produces identical output 3 rounds
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

from nines.sandbox.isolation import (
    EnvironmentSnapshot,
    PollutionDetector,
    PollutionReport,
    VenvFactory,
)
from nines.sandbox.manager import SandboxConfig, SandboxContext, SandboxManager
from nines.sandbox.runner import IsolatedRunner, RunResult


@pytest.fixture()
def manager(tmp_path: Path) -> SandboxManager:
    mgr = SandboxManager(base_dir=tmp_path / "sandboxes")
    yield mgr
    mgr.destroy_all()


# ---------------------------------------------------------------------------
# 1. No system pollution
# ---------------------------------------------------------------------------


class TestNoSystemPollution:
    """Host environment must not change after sandbox execution."""

    def test_env_unchanged_after_execution(
        self, manager: SandboxManager, tmp_path: Path,
    ) -> None:
        watch_dir = tmp_path / "watched"
        watch_dir.mkdir()
        watch_file = tmp_path / "watched_file.txt"
        watch_file.write_text("original", encoding="utf-8")

        detector = PollutionDetector(
            watched_dirs=[watch_dir], watched_files=[watch_file],
        )
        detector.snapshot_before()

        ctx = manager.create()
        script = ctx.work_dir / "polluter.py"
        script.write_text(
            textwrap.dedent("""\
                import os
                os.environ["POLLUTED"] = "yes"
                with open("sandbox_file.txt", "w") as f:
                    f.write("sandbox data")
            """),
            encoding="utf-8",
        )
        result = manager.run_in_sandbox(ctx, [sys.executable, str(script)])
        assert result.exit_code == 0
        manager.destroy(ctx)

        detector.snapshot_after()
        report = detector.detect_pollution()

        assert report.is_clean is True, (
            f"Pollution detected after sandbox execution: {report.changes}"
        )

    def test_sandbox_files_dont_leak(self, manager: SandboxManager) -> None:
        ctx = manager.create()
        secret_file = ctx.work_dir / "secret.txt"
        secret_file.write_text("confidential", encoding="utf-8")

        work_dir = ctx.work_dir
        manager.destroy(ctx)

        assert not work_dir.exists(), "Sandbox work dir should be removed on destroy"

    def test_sys_path_unchanged(self, manager: SandboxManager) -> None:
        original_path = list(sys.path)

        ctx = manager.create()
        script = ctx.work_dir / "path_modifier.py"
        script.write_text("import sys; sys.path.append('/bogus')\n", encoding="utf-8")
        manager.run_in_sandbox(ctx, [sys.executable, str(script)])
        manager.destroy(ctx)

        assert sys.path == original_path, "sys.path should not change in parent process"


# ---------------------------------------------------------------------------
# 2. No cross-pollution between sandboxes
# ---------------------------------------------------------------------------


class TestNoCrossPollution:
    """Sandboxes must be completely isolated from each other."""

    def test_file_isolation_bidirectional(self, manager: SandboxManager) -> None:
        ctx_a = manager.create()
        ctx_b = manager.create()

        try:
            (ctx_a.work_dir / "file_a.txt").write_text("data_a", encoding="utf-8")
            (ctx_b.work_dir / "file_b.txt").write_text("data_b", encoding="utf-8")

            script_a = ctx_a.work_dir / "check.py"
            script_a.write_text("import os; print(os.listdir('.'))", encoding="utf-8")
            result_a = manager.run_in_sandbox(ctx_a, [sys.executable, str(script_a)])

            script_b = ctx_b.work_dir / "check.py"
            script_b.write_text("import os; print(os.listdir('.'))", encoding="utf-8")
            result_b = manager.run_in_sandbox(ctx_b, [sys.executable, str(script_b)])

            assert "file_b.txt" not in result_a.stdout, "Sandbox A sees B's files"
            assert "file_a.txt" not in result_b.stdout, "Sandbox B sees A's files"
        finally:
            manager.destroy(ctx_a)
            manager.destroy(ctx_b)

    def test_env_var_isolation_between_sandboxes(self, manager: SandboxManager) -> None:
        ctx_a = manager.create(SandboxConfig(seed=1))
        ctx_b = manager.create(SandboxConfig(seed=2))

        try:
            script = textwrap.dedent("""\
                import os
                print(os.environ.get("NINES_SEED", "NONE"))
            """)
            script_a = ctx_a.work_dir / "env_check.py"
            script_a.write_text(script, encoding="utf-8")
            script_b = ctx_b.work_dir / "env_check.py"
            script_b.write_text(script, encoding="utf-8")

            result_a = manager.run_in_sandbox(ctx_a, [sys.executable, str(script_a)], seed=1)
            result_b = manager.run_in_sandbox(ctx_b, [sys.executable, str(script_b)], seed=2)

            assert result_a.stdout.strip() == "1"
            assert result_b.stdout.strip() == "2"
        finally:
            manager.destroy(ctx_a)
            manager.destroy(ctx_b)

    def test_concurrent_sandboxes_no_interference(self, manager: SandboxManager) -> None:
        contexts = [manager.create() for _ in range(4)]
        try:
            for i, ctx in enumerate(contexts):
                (ctx.work_dir / f"marker_{i}.txt").write_text(f"ctx_{i}", encoding="utf-8")

            for i, ctx in enumerate(contexts):
                files = list(ctx.work_dir.iterdir())
                file_names = [f.name for f in files]
                assert f"marker_{i}.txt" in file_names
                for j in range(4):
                    if j != i:
                        assert f"marker_{j}.txt" not in file_names
        finally:
            for ctx in contexts:
                manager.destroy(ctx)


# ---------------------------------------------------------------------------
# 3. Deterministic re-test (same seed, 3 rounds)
# ---------------------------------------------------------------------------


class TestDeterministicRetest:
    """Same seed must produce identical results across multiple runs."""

    def test_three_rounds_same_seed(self, manager: SandboxManager) -> None:
        script_src = textwrap.dedent("""\
            import random, os, hashlib
            seed = int(os.environ.get("NINES_SEED", "0"))
            random.seed(seed)
            values = [str(random.random()) for _ in range(10)]
            output = ",".join(values)
            print(output)
        """)

        fingerprints: list[str] = []
        outputs: list[str] = []

        for round_num in range(3):
            ctx = manager.create(SandboxConfig(seed=42))
            try:
                script = ctx.work_dir / "deterministic.py"
                script.write_text(script_src, encoding="utf-8")
                result = manager.run_in_sandbox(
                    ctx, [sys.executable, str(script)], seed=42,
                )
                assert result.exit_code == 0, (
                    f"Round {round_num} failed: {result.stderr}"
                )
                fingerprints.append(result.fingerprint)
                outputs.append(result.stdout.strip())
            finally:
                manager.destroy(ctx)

        assert len(set(fingerprints)) == 1, (
            f"Fingerprints differ across 3 rounds: {fingerprints}"
        )
        assert len(set(outputs)) == 1, (
            f"Outputs differ across 3 rounds: {outputs}"
        )

    def test_different_seeds_produce_different_results(
        self, manager: SandboxManager,
    ) -> None:
        script_src = textwrap.dedent("""\
            import random, os
            seed = int(os.environ.get("NINES_SEED", "0"))
            random.seed(seed)
            print(random.random())
        """)

        results_by_seed: dict[int, str] = {}
        for seed in [1, 2, 3]:
            ctx = manager.create(SandboxConfig(seed=seed))
            try:
                script = ctx.work_dir / "seeded.py"
                script.write_text(script_src, encoding="utf-8")
                result = manager.run_in_sandbox(
                    ctx, [sys.executable, str(script)], seed=seed,
                )
                assert result.exit_code == 0
                results_by_seed[seed] = result.stdout.strip()
            finally:
                manager.destroy(ctx)

        assert len(set(results_by_seed.values())) == 3, (
            f"Different seeds should produce different outputs: {results_by_seed}"
        )

    def test_determinism_with_hashseed(self, manager: SandboxManager) -> None:
        script_src = textwrap.dedent("""\
            import os
            print(os.environ.get("PYTHONHASHSEED", "UNSET"))
            print(os.environ.get("NINES_SEED", "UNSET"))
        """)

        for _ in range(2):
            ctx = manager.create(SandboxConfig(seed=123))
            try:
                script = ctx.work_dir / "hashseed.py"
                script.write_text(script_src, encoding="utf-8")
                result = manager.run_in_sandbox(
                    ctx, [sys.executable, str(script)], seed=123,
                )
                assert result.exit_code == 0
                lines = result.stdout.strip().splitlines()
                assert lines[0] == "123"
                assert lines[1] == "123"
            finally:
                manager.destroy(ctx)


# ---------------------------------------------------------------------------
# PollutionDetector comprehensive integration
# ---------------------------------------------------------------------------


class TestPollutionDetectorIntegration:
    """Comprehensive pollution detection scenarios."""

    def test_dir_listing_pollution(self, tmp_path: Path) -> None:
        watch_dir = tmp_path / "watched"
        watch_dir.mkdir()
        (watch_dir / "existing.txt").write_text("ok", encoding="utf-8")

        detector = PollutionDetector(watched_dirs=[watch_dir])
        detector.snapshot_before()

        (watch_dir / "intruder.txt").write_text("bad", encoding="utf-8")

        detector.snapshot_after()
        report = detector.detect_pollution()
        assert not report.is_clean
        assert any("intruder" in str(c) for c in report.changes.get("dirs", []))

    def test_file_hash_change_detected(self, tmp_path: Path) -> None:
        watch_file = tmp_path / "config.txt"
        watch_file.write_text("version=1", encoding="utf-8")

        detector = PollutionDetector(watched_files=[watch_file])
        detector.snapshot_before()

        watch_file.write_text("version=2", encoding="utf-8")

        detector.snapshot_after()
        report = detector.detect_pollution()
        assert not report.is_clean
        assert "files" in report.changes

    def test_clean_execution_no_side_effects(self, tmp_path: Path) -> None:
        watch_dir = tmp_path / "clean_dir"
        watch_dir.mkdir()

        detector = PollutionDetector(watched_dirs=[watch_dir])
        detector.snapshot_before()
        detector.snapshot_after()
        report = detector.detect_pollution()
        assert report.is_clean
        assert report.total_changes == 0
