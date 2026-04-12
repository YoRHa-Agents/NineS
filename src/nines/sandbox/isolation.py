"""Isolation utilities: VenvFactory and PollutionDetector.

VenvFactory manages virtual environment lifecycle (create, destroy, install).
PollutionDetector snapshots host state and diffs before/after to verify
sandbox execution did not modify the host environment.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("nines.sandbox.isolation")


# ---------------------------------------------------------------------------
# VenvFactory
# ---------------------------------------------------------------------------


class VenvFactory:
    """Create and manage isolated Python virtual environments.

    Prefers ``uv`` for fast creation when available, falls back to
    stdlib ``venv.EnvBuilder``.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._use_uv = shutil.which("uv") is not None

    # -- public API ---------------------------------------------------------

    def create_venv(self, path: Path) -> Path:
        """Create a virtual environment at *path* and return its root."""
        if self._use_uv:
            self._create_with_uv(path)
        else:
            self._create_with_stdlib(path)
        return path

    def destroy_venv(self, path: Path) -> None:
        """Remove a virtual environment completely."""
        if path.exists():
            shutil.rmtree(path)

    def install_packages(self, venv_path: Path, packages: list[str]) -> None:
        """Install *packages* into the venv at *venv_path*."""
        if not packages:
            return
        if self._use_uv:
            subprocess.run(
                [
                    "uv", "pip", "install",
                    "--python", str(self.python_path(venv_path)),
                    *packages,
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        else:
            pip = self._pip_path(venv_path)
            subprocess.run(
                [str(pip), "install", "--quiet", *packages],
                check=True,
                capture_output=True,
                timeout=120,
            )

    def python_path(self, venv_path: Path) -> Path:
        """Return the Python interpreter path inside *venv_path*."""
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    # -- private helpers ----------------------------------------------------

    def _create_with_uv(self, venv_path: Path) -> None:
        subprocess.run(
            ["uv", "venv", str(venv_path), "--seed"],
            check=True,
            capture_output=True,
            timeout=30,
        )

    def _create_with_stdlib(self, venv_path: Path) -> None:
        builder = venv.EnvBuilder(
            system_site_packages=False,
            clear=True,
            with_pip=True,
        )
        builder.create(str(venv_path))

    def _pip_path(self, venv_path: Path) -> Path:
        if sys.platform == "win32":
            return venv_path / "Scripts" / "pip.exe"
        return venv_path / "bin" / "pip"


# ---------------------------------------------------------------------------
# EnvironmentSnapshot / PollutionReport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Immutable snapshot of observable host state."""

    env_vars: dict[str, str]
    watched_file_hashes: dict[str, str]
    watched_dir_listings: dict[str, tuple[str, ...]]
    python_path: tuple[str, ...]
    cwd: str


@dataclass(frozen=True)
class PollutionReport:
    """Result of comparing two environment snapshots."""

    is_clean: bool
    changes: dict[str, list[str]]

    @property
    def total_changes(self) -> int:
        return sum(len(v) for v in self.changes.values())


# ---------------------------------------------------------------------------
# PollutionDetector
# ---------------------------------------------------------------------------


class PollutionDetector:
    """Detect host environment changes caused by sandbox execution.

    Takes before/after snapshots and diffs across four dimensions:
    environment variables, watched files, watched directories, and sys.path.
    """

    def __init__(
        self,
        watched_dirs: list[Path] | None = None,
        watched_files: list[Path] | None = None,
    ) -> None:
        self._watched_dirs = watched_dirs or []
        self._watched_files = watched_files or []
        self._before: EnvironmentSnapshot | None = None
        self._after: EnvironmentSnapshot | None = None

    def snapshot(self) -> EnvironmentSnapshot:
        """Capture current host environment state."""
        file_hashes: dict[str, str] = {}
        for f in self._watched_files:
            if f.exists():
                file_hashes[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()

        dir_listings: dict[str, tuple[str, ...]] = {}
        for d in self._watched_dirs:
            if d.exists():
                dir_listings[str(d)] = tuple(
                    sorted(str(p) for p in d.rglob("*"))
                )

        return EnvironmentSnapshot(
            env_vars=dict(os.environ),
            watched_file_hashes=file_hashes,
            watched_dir_listings=dir_listings,
            python_path=tuple(sys.path),
            cwd=os.getcwd(),
        )

    def snapshot_before(self) -> EnvironmentSnapshot:
        """Take the *before* snapshot and store it internally."""
        self._before = self.snapshot()
        return self._before

    def snapshot_after(self) -> EnvironmentSnapshot:
        """Take the *after* snapshot and store it internally."""
        self._after = self.snapshot()
        return self._after

    def detect_pollution(self) -> PollutionReport:
        """Compare stored before/after snapshots and return a report."""
        if self._before is None or self._after is None:
            raise RuntimeError(
                "Must call snapshot_before() and snapshot_after() first"
            )
        return self.compare(self._before, self._after)

    def compare(
        self,
        before: EnvironmentSnapshot,
        after: EnvironmentSnapshot,
    ) -> PollutionReport:
        """Compare two snapshots to detect host environment changes."""
        changes: dict[str, list[str]] = {
            "env_vars": self._diff_dicts(before.env_vars, after.env_vars, "env"),
            "files": self._diff_dicts(
                before.watched_file_hashes, after.watched_file_hashes, "file"
            ),
            "dirs": self._diff_dir_listings(
                before.watched_dir_listings, after.watched_dir_listings
            ),
            "sys_path": self._diff_sequences(
                before.python_path, after.python_path, "sys.path"
            ),
        }
        non_empty = {k: v for k, v in changes.items() if v}
        is_clean = len(non_empty) == 0
        if not is_clean:
            logger.warning("Pollution detected: %s", non_empty)
        return PollutionReport(is_clean=is_clean, changes=non_empty)

    # -- diff helpers -------------------------------------------------------

    @staticmethod
    def _diff_dicts(
        before: dict[str, str], after: dict[str, str], label: str,
    ) -> list[str]:
        changes: list[str] = []
        for key in set(before) | set(after):
            old, new = before.get(key), after.get(key)
            if old != new:
                if old is None:
                    changes.append(f"ADDED {label} {key}={new!r}")
                elif new is None:
                    changes.append(f"REMOVED {label} {key}")
                else:
                    changes.append(f"MODIFIED {label} {key}: {old!r} -> {new!r}")
        return changes

    @staticmethod
    def _diff_dir_listings(
        before: dict[str, tuple[str, ...]],
        after: dict[str, tuple[str, ...]],
    ) -> list[str]:
        changes: list[str] = []
        for d in set(before) | set(after):
            old_set = set(before.get(d, ()))
            new_set = set(after.get(d, ()))
            added = new_set - old_set
            removed = old_set - new_set
            if added:
                changes.append(f"ADDED in {d}: {sorted(added)}")
            if removed:
                changes.append(f"REMOVED in {d}: {sorted(removed)}")
        return changes

    @staticmethod
    def _diff_sequences(
        before: tuple[str, ...], after: tuple[str, ...], label: str,
    ) -> list[str]:
        changes: list[str] = []
        added = set(after) - set(before)
        removed = set(before) - set(after)
        if added:
            changes.append(f"{label} ADDED: {sorted(added)}")
        if removed:
            changes.append(f"{label} REMOVED: {sorted(removed)}")
        return changes
