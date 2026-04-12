"""SandboxManager — lifecycle management for isolated execution sandboxes.

Creates isolated environments (tmpdir + optional venv), tracks active
sandboxes, enforces a max-concurrent limit, and exposes context-manager
support for automatic cleanup.
"""

from __future__ import annotations

import atexit
import logging
import shutil
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from nines.sandbox.isolation import VenvFactory
from nines.sandbox.runner import IsolatedRunner, RunResult

logger = logging.getLogger("nines.sandbox.manager")


@dataclass
class SandboxConfig:
    """Configuration for a single sandbox instance."""

    timeout_seconds: int = 30
    seed: int | None = None
    use_venv: bool = False
    requirements: list[str] = field(default_factory=list)
    keep_on_failure: bool = False
    max_memory_mb: int = 512
    env_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxContext:
    """Handle to an active sandbox."""

    sandbox_id: str
    work_dir: Path
    venv_path: Path | None
    python_path: Path
    config: SandboxConfig
    created_at: float  # time.monotonic()


class SandboxManager:
    """Create, track, and destroy isolated execution sandboxes.

    Features:
    - ``create(config)`` → ``SandboxContext``
    - ``destroy(context)`` cleans up workspace (and venv if created)
    - Context-manager support via ``__enter__`` / ``__exit__``
    - Tracks active sandboxes; enforces ``max_concurrent``
    - Registers ``destroy_all`` with ``atexit`` as a safety net
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        max_concurrent: int = 8,
    ) -> None:
        self._base_dir = base_dir or Path(tempfile.gettempdir()) / "nines_sandboxes"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._venv_factory = VenvFactory(self._base_dir / "venvs")
        self._runner = IsolatedRunner()
        self._active: dict[str, SandboxContext] = {}
        self._max_concurrent = max_concurrent
        self._lock = threading.Lock()

        atexit.register(self.destroy_all)

    # -- lifecycle ----------------------------------------------------------

    def create(self, config: SandboxConfig | None = None) -> SandboxContext:
        """Create a new isolated sandbox and return its context.

        Raises
        ------
        RuntimeError
            If the maximum number of concurrent sandboxes is reached.
        """
        config = config or SandboxConfig()

        with self._lock:
            if len(self._active) >= self._max_concurrent:
                raise RuntimeError(
                    f"Max concurrent sandboxes ({self._max_concurrent}) reached. "
                    "Destroy an existing sandbox first."
                )

        sandbox_id = uuid.uuid4().hex[:12]
        work_dir = self._base_dir / "workspaces" / sandbox_id
        work_dir.mkdir(parents=True, exist_ok=True)

        venv_path: Path | None = None
        python_path = Path(sys.executable)

        if config.use_venv:
            venv_path = self._base_dir / "venvs" / sandbox_id
            self._venv_factory.create_venv(venv_path)
            python_path = self._venv_factory.python_path(venv_path)
            if config.requirements:
                self._venv_factory.install_packages(venv_path, config.requirements)

        ctx = SandboxContext(
            sandbox_id=sandbox_id,
            work_dir=work_dir,
            venv_path=venv_path,
            python_path=python_path,
            config=config,
            created_at=time.monotonic(),
        )

        with self._lock:
            self._active[sandbox_id] = ctx

        logger.info("Sandbox created: %s at %s", sandbox_id, work_dir)
        return ctx

    def destroy(self, context: SandboxContext) -> None:
        """Tear down a sandbox, removing its workspace and optional venv."""
        sid = context.sandbox_id

        with self._lock:
            self._active.pop(sid, None)

        if not context.config.keep_on_failure:
            if context.work_dir.exists():
                shutil.rmtree(context.work_dir, ignore_errors=True)

        if context.venv_path is not None:
            self._venv_factory.destroy_venv(context.venv_path)

        logger.info("Sandbox destroyed: %s", sid)

    def destroy_all(self) -> None:
        """Tear down every active sandbox (used by atexit and tests)."""
        with self._lock:
            contexts = list(self._active.values())
        for ctx in contexts:
            try:
                self.destroy(ctx)
            except Exception:
                logger.exception("Failed to destroy sandbox %s", ctx.sandbox_id)

    def run_in_sandbox(
        self,
        context: SandboxContext,
        command: list[str],
        timeout: int | None = None,
        seed: int | None = None,
    ) -> RunResult:
        """Convenience: run *command* inside *context* via IsolatedRunner."""
        effective_timeout = timeout or context.config.timeout_seconds
        effective_seed = seed if seed is not None else context.config.seed
        return self._runner.run(
            command=command,
            sandbox_context=context,
            timeout=effective_timeout,
            seed=effective_seed,
        )

    # -- properties ---------------------------------------------------------

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    @property
    def active_sandboxes(self) -> dict[str, SandboxContext]:
        with self._lock:
            return dict(self._active)

    # -- context manager ----------------------------------------------------

    def __enter__(self) -> SandboxManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        self.destroy_all()
        return None
