"""IsolatedRunner — execute commands inside a sandbox subprocess.

Captures stdout, stderr, exit_code, and wall-clock duration.
Sets determinism-related environment variables (PYTHONHASHSEED, NINES_SEED)
and enforces timeout via ``subprocess.run(timeout=…)``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

logger = logging.getLogger("nines.sandbox.runner")


@dataclass(frozen=True)
class RunResult:
    """Captured output from an isolated execution."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timed_out: bool
    fingerprint: str  # SHA-256 of (exit_code, stdout, stderr)


class IsolatedRunner:
    """Execute commands inside a sandbox subprocess with resource controls.

    The runner:
    - Runs a command list via ``subprocess.run`` in the sandbox's tmpdir.
    - Sets PYTHONHASHSEED, NINES_SEED, PYTHONDONTWRITEBYTECODE, and
      an isolated PATH (sandbox venv bin prepended).
    - Captures stdout, stderr, and exit_code.
    - Enforces wall-clock timeout.
    """

    def run(
        self,
        command: list[str],
        sandbox_context: SandboxContext,
        timeout: int = 30,
        seed: int | None = None,
    ) -> RunResult:
        """Execute *command* inside *sandbox_context*.

        Parameters
        ----------
        command:
            Argv list, e.g. ``["python", "script.py"]``.
        sandbox_context:
            The :class:`SandboxContext` providing ``work_dir``, ``venv_path``,
            and ``python_path``.
        timeout:
            Maximum wall-clock seconds before SIGKILL.
        seed:
            If provided, sets PYTHONHASHSEED and NINES_SEED for determinism.

        Returns
        -------
        RunResult
            Captured execution outcome.
        """
        env = self._build_env(sandbox_context, seed)
        start = time.monotonic()
        timed_out = False

        try:
            proc = subprocess.run(
                command,
                cwd=str(sandbox_context.work_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                start_new_session=True,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            if isinstance(exc.stdout, bytes):
                stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
            else:
                stdout = exc.stdout or ""
            if isinstance(exc.stderr, bytes):
                stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
            else:
                stderr = exc.stderr or ""
            logger.warning(
                "Command timed out after %ds in sandbox %s",
                timeout,
                sandbox_context.sandbox_id,
            )

        duration_ms = (time.monotonic() - start) * 1000
        fingerprint = _compute_fingerprint(exit_code, stdout, stderr)

        return RunResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _build_env(
        ctx: SandboxContext, seed: int | None,
    ) -> dict[str, str]:
        """Build an isolated environment dict for the subprocess."""
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        if seed is not None:
            env["PYTHONHASHSEED"] = str(seed)
            env["NINES_SEED"] = str(seed)
        else:
            env["PYTHONHASHSEED"] = "0"

        if ctx.venv_path is not None:
            venv_bin = str(ctx.venv_path / "bin")
            env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = str(ctx.venv_path)

        return env


def _compute_fingerprint(exit_code: int, stdout: str, stderr: str) -> str:
    """SHA-256 hash of execution output for determinism verification."""
    content = json.dumps(
        {"exit_code": exit_code, "stdout": stdout.strip(), "stderr": stderr.strip()},
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


# Avoid circular import at module level — SandboxContext is used only for
# type annotations and is resolved at runtime by the caller.
if TYPE_CHECKING:
    from nines.sandbox.manager import SandboxContext
