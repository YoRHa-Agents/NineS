# NineS Sandbox Design

> **Task**: T16 — Lightweight Sandbox for Isolated Evaluation Execution
> **Input**: `docs/design/requirements.md` (NFR-09–NFR-12, FR-114, FR-116), `docs/research/domain_knowledge.md` §4
> **Consumers**: `src/nines/sandbox/` implementation, `src/nines/eval/runner.py`
> **Last Modified**: 2026-04-11

---

## Table of Contents

1. [Overview](#1-overview)
2. [Three-Layer Isolation Model](#2-three-layer-isolation-model)
3. [Core Interfaces](#3-core-interfaces)
4. [SandboxManager](#4-sandboxmanager)
5. [IsolatedRunner](#5-isolatedrunner)
6. [VenvFactory](#6-venvfactory)
7. [Result Capture](#7-result-capture)
8. [Determinism and Seed Control](#8-determinism-and-seed-control)
9. [Pollution Detection](#9-pollution-detection)
10. [Multi-Round Convergence](#10-multi-round-convergence)
11. [Lifecycle and Resource Management](#11-lifecycle-and-resource-management)
12. [Configuration](#12-configuration)
13. [Requirement Traceability](#13-requirement-traceability)

---

## 1. Overview

The sandbox subsystem provides **lightweight, Docker-free isolated execution** for NineS evaluation tasks. It prevents evaluated code from polluting the host environment while maintaining deterministic, reproducible results.

### Design Goals

| Goal | Description | Driving Requirements |
|------|-------------|---------------------|
| **Host Isolation** | Evaluated code cannot modify the host filesystem, environment, or Python path | NFR-09, NFR-10 |
| **Determinism** | Same seed + same task = identical output across runs | NFR-11, NFR-12 |
| **Low Overhead** | ≤5s cold venv creation, ≤1s warm pool reuse | NFR-02 |
| **Pollution Detection** | Before/after diff proves isolation held | NFR-09, FR-116 |
| **Multi-Round Stability** | CV ≤ 5% across repeated runs of deterministic tasks | NFR-11, FR-411 |
| **No Docker Dependency** | MVP uses stdlib + `uv`; Docker is a future Tier 2 extension | CON-05 |

### Architecture Position

```
EvalRunner → SandboxManager → VenvFactory (environment layer)
                            → IsolatedRunner (process layer)
                            → tmpdir workspace (filesystem layer)
                            → PollutionDetector (verification layer)
```

The sandbox sits between the evaluation orchestrator (`EvalRunner`) and actual code execution. The orchestrator never runs task code directly — it always delegates through `SandboxManager`.

---

## 2. Three-Layer Isolation Model

Each sandbox provides three orthogonal isolation layers, any of which can be used independently but are designed for composition:

```
┌─────────────────────────────────────────────┐
│  Layer 3: Filesystem Isolation (tmpdir)      │
│  ┌───────────────────────────────────────┐  │
│  │  Layer 2: Environment Isolation (venv) │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │  Layer 1: Process Isolation      │  │  │
│  │  │  (subprocess + resource limits)  │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### Layer 1: Process Isolation (`subprocess`)

Task code runs in a **child process** with:
- Separate PID and process group (enables clean SIGKILL on timeout)
- `resource.setrlimit(RLIMIT_AS, ...)` capping virtual memory (Linux)
- `subprocess.run(..., timeout=N)` enforcing wall-clock timeout
- Inherited stdout/stderr captured as byte streams, decoded to UTF-8
- `PYTHONDONTWRITEBYTECODE=1` suppressing `.pyc` creation on host

### Layer 2: Environment Isolation (`venv`)

Each sandbox gets a **dedicated virtual environment** so that:
- Package installs are scoped to the sandbox (no host `site-packages` mutation)
- The Python interpreter path is sandbox-local (`<venv>/bin/python`)
- `sys.path` in the child process excludes host packages
- `uv` is used for venv creation when available (10–100x faster than `venv` module)

### Layer 3: Filesystem Isolation (`tmpdir`)

Each sandbox gets a **dedicated temporary directory** as its working directory:
- Created via `tempfile.mkdtemp(prefix="nines_sandbox_")`
- Task scripts and input files are copied into the tmpdir before execution
- The child process `cwd` is set to the tmpdir
- On teardown, `shutil.rmtree()` removes all sandbox artifacts
- Optional `keep_on_failure` flag preserves the tmpdir for debugging

---

## 3. Core Interfaces

All sandbox components are defined as Python Protocol classes for structural subtyping (CON-09).

```python
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class IsolationLevel(enum.Enum):
    """Configurable isolation tiers."""
    NONE = "none"
    PROCESS = "process"
    VENV = "venv"
    FULL = "full"  # process + venv + tmpdir (default)


@dataclass(frozen=True)
class SandboxConfig:
    """Immutable configuration for a single sandbox instance."""
    timeout_seconds: int = 30
    max_memory_mb: int = 512
    requirements: tuple[str, ...] = ()
    seed: int | None = None
    isolation: IsolationLevel = IsolationLevel.FULL
    keep_on_failure: bool = False
    env_overrides: dict[str, str] = field(default_factory=dict)
    python_version: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Captured output from an isolated execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    memory_exceeded: bool
    sandbox_id: str
    fingerprint: str  # SHA-256 of (exit_code, stdout, stderr)


@dataclass
class SandboxHandle:
    """Opaque handle to an active sandbox."""
    id: str
    workspace: Path
    venv_path: Path | None
    python_path: Path
    config: SandboxConfig
    created_at: float  # time.monotonic()


@runtime_checkable
class SandboxManagerProtocol(Protocol):
    """Lifecycle management for sandbox instances."""

    def create(self, config: SandboxConfig | None = None) -> SandboxHandle: ...
    def execute(self, handle: SandboxHandle, script: str) -> ExecutionResult: ...
    def execute_file(self, handle: SandboxHandle, path: Path) -> ExecutionResult: ...
    def destroy(self, sandbox_id: str) -> None: ...
    def destroy_all(self) -> None: ...


@runtime_checkable
class IsolatedRunnerProtocol(Protocol):
    """Low-level subprocess execution with resource limits."""

    def run(
        self,
        python_path: Path,
        script_path: Path,
        working_dir: Path,
        *,
        timeout: int = 30,
        max_memory_mb: int = 512,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult: ...


@runtime_checkable
class VenvFactoryProtocol(Protocol):
    """Create and manage isolated Python virtual environments."""

    def create(
        self,
        name: str,
        requirements: tuple[str, ...] = (),
    ) -> Path: ...

    def destroy(self, name: str) -> None: ...

    def python_path(self, venv_path: Path) -> Path: ...


@runtime_checkable
class PollutionDetectorProtocol(Protocol):
    """Before/after diff to verify host was not modified."""

    def snapshot(self) -> EnvironmentSnapshot: ...
    def compare(
        self, before: EnvironmentSnapshot, after: EnvironmentSnapshot
    ) -> PollutionReport: ...
```

---

## 4. SandboxManager

The `SandboxManager` is the primary entry point for creating, using, and tearing down sandboxes. It composes the three isolation layers and manages their lifecycle.

### 4.1 Class Design

```python
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from nines.core.errors import SandboxError, SandboxTimeoutError
from nines.core.events import EventBus, EventType


class SandboxManager:
    """Lifecycle management for isolated execution sandboxes.

    Composes VenvFactory, IsolatedRunner, and PollutionDetector
    into a unified sandbox lifecycle.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        venv_factory: VenvFactoryProtocol | None = None,
        runner: IsolatedRunnerProtocol | None = None,
        pollution_detector: PollutionDetectorProtocol | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._base_dir = base_dir or Path(tempfile.gettempdir()) / "nines_sandboxes"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._venv_factory = venv_factory or VenvFactory(self._base_dir / "venvs")
        self._runner = runner or IsolatedRunner()
        self._detector = pollution_detector or PollutionDetector()
        self._event_bus = event_bus
        self._active: dict[str, SandboxHandle] = {}

    def create(self, config: SandboxConfig | None = None) -> SandboxHandle:
        """Create a new sandbox with isolated workspace and optional venv."""
        config = config or SandboxConfig()
        sandbox_id = uuid.uuid4().hex[:12]

        workspace = self._base_dir / "workspaces" / sandbox_id
        workspace.mkdir(parents=True, exist_ok=True)

        venv_path: Path | None = None
        python_path: Path

        if config.isolation in (IsolationLevel.VENV, IsolationLevel.FULL):
            venv_path = self._venv_factory.create(
                name=sandbox_id,
                requirements=config.requirements,
            )
            python_path = self._venv_factory.python_path(venv_path)
        else:
            import sys
            python_path = Path(sys.executable)

        handle = SandboxHandle(
            id=sandbox_id,
            workspace=workspace,
            venv_path=venv_path,
            python_path=python_path,
            config=config,
            created_at=time.monotonic(),
        )
        self._active[sandbox_id] = handle
        self._emit(EventType.SANDBOX_CREATED, {"sandbox_id": sandbox_id})
        return handle

    def execute(self, handle: SandboxHandle, script: str) -> ExecutionResult:
        """Write script to workspace and execute inside the sandbox."""
        script_path = handle.workspace / "_nines_run.py"
        effective_script = self._prepend_seed_init(script, handle.config.seed)
        script_path.write_text(effective_script, encoding="utf-8")
        return self.execute_file(handle, script_path)

    def execute_file(self, handle: SandboxHandle, path: Path) -> ExecutionResult:
        """Execute an existing script file inside the sandbox."""
        env = _build_sandbox_env(handle.config)
        working_dir = (
            handle.workspace
            if handle.config.isolation in (IsolationLevel.FULL,)
            else path.parent
        )
        result = self._runner.run(
            python_path=handle.python_path,
            script_path=path,
            working_dir=working_dir,
            timeout=handle.config.timeout_seconds,
            max_memory_mb=handle.config.max_memory_mb,
            env=env,
        )
        self._emit(EventType.SANDBOX_EXECUTION_COMPLETE, {
            "sandbox_id": handle.id,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "timed_out": result.timed_out,
        })
        return result

    def execute_with_pollution_check(
        self,
        handle: SandboxHandle,
        script: str,
        watched_dirs: list[Path] | None = None,
        watched_files: list[Path] | None = None,
    ) -> tuple[ExecutionResult, PollutionReport]:
        """Execute in sandbox and verify no host pollution occurred."""
        before = self._detector.snapshot()
        result = self.execute(handle, script)
        after = self._detector.snapshot()
        report = self._detector.compare(before, after)

        if not report.clean:
            import logging
            logging.getLogger("nines.sandbox").error(
                "Sandbox %s caused host pollution: env=%d files=%d dirs=%d path=%d",
                handle.id,
                len(report.env_var_changes),
                len(report.file_changes),
                len(report.dir_changes),
                len(report.path_changes),
            )
        return result, report

    def destroy(self, sandbox_id: str) -> None:
        """Clean up all sandbox resources."""
        handle = self._active.pop(sandbox_id, None)
        if handle is None:
            return
        if not handle.config.keep_on_failure:
            shutil.rmtree(handle.workspace, ignore_errors=True)
        if handle.venv_path is not None:
            self._venv_factory.destroy(sandbox_id)
        self._emit(EventType.SANDBOX_DESTROYED, {"sandbox_id": sandbox_id})

    def destroy_all(self) -> None:
        """Tear down all active sandboxes."""
        for sid in list(self._active):
            self.destroy(sid)

    def _prepend_seed_init(self, script: str, seed: int | None) -> str:
        if seed is None:
            return script
        return _seed_init_snippet(seed) + "\n" + script

    def _emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        if self._event_bus is not None:
            self._event_bus.emit(event_type, data)
```

### 4.2 Context Manager Support

```python
from contextlib import contextmanager
from typing import Generator


@contextmanager
def sandbox_scope(
    manager: SandboxManager,
    config: SandboxConfig | None = None,
) -> Generator[SandboxHandle, None, None]:
    """Context manager that creates and automatically destroys a sandbox."""
    handle = manager.create(config)
    try:
        yield handle
    finally:
        manager.destroy(handle.id)
```

---

## 5. IsolatedRunner

The `IsolatedRunner` handles the low-level subprocess execution with timeout enforcement and resource limits.

### 5.1 Class Design

```python
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path


class IsolatedRunner:
    """Execute Python scripts in isolated subprocesses with resource limits.

    Captures stdout, stderr, exit code, and timing. Enforces timeout
    via subprocess.run() and memory limits via resource.setrlimit().
    """

    def run(
        self,
        python_path: Path,
        script_path: Path,
        working_dir: Path,
        *,
        timeout: int = 30,
        max_memory_mb: int = 512,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        effective_env = os.environ.copy()
        effective_env["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            effective_env.update(env)

        start = time.monotonic()
        timed_out = False
        memory_exceeded = False

        try:
            proc = subprocess.run(
                [str(python_path), str(script_path)],
                cwd=str(working_dir),
                env=effective_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=_make_resource_limiter(max_memory_mb),
                start_new_session=True,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
            _kill_process_group(exc)
        except MemoryError:
            memory_exceeded = True
            exit_code = -2
            stdout = ""
            stderr = "MemoryError: sandbox memory limit exceeded"

        duration_ms = (time.monotonic() - start) * 1000
        fingerprint = _compute_fingerprint(exit_code, stdout, stderr)

        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            memory_exceeded=memory_exceeded,
            sandbox_id="",  # filled by SandboxManager
            fingerprint=fingerprint,
        )


def _make_resource_limiter(max_memory_mb: int):
    """Return a preexec_fn that sets RLIMIT_AS on Linux."""
    def _set_limits() -> None:
        try:
            import resource
            mem_bytes = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ImportError, ValueError, OSError):
            pass
    return _set_limits


def _kill_process_group(exc: subprocess.TimeoutExpired) -> None:
    """Send SIGKILL to the entire process group on timeout."""
    if exc.args and hasattr(exc, "cmd"):
        try:
            pgid = os.getpgid(exc.args[0] if isinstance(exc.args[0], int) else 0)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _compute_fingerprint(exit_code: int, stdout: str, stderr: str) -> str:
    """SHA-256 hash of execution output for determinism verification."""
    content = json.dumps(
        {"exit_code": exit_code, "stdout": stdout.strip(), "stderr": stderr.strip()},
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()
```

### 5.2 Process Group Isolation

Using `start_new_session=True` creates a new process group for the child. On timeout, `_kill_process_group` sends SIGKILL to the entire group, ensuring any grandchild processes spawned by the evaluation script are also terminated. This prevents orphaned processes from accumulating across evaluation runs.

---

## 6. VenvFactory

The `VenvFactory` manages virtual environment creation and teardown. It prefers `uv` for speed (CON-02) but falls back to stdlib `venv` when `uv` is unavailable.

### 6.1 Class Design

```python
import shutil
import subprocess
import sys
import venv
from pathlib import Path


class VenvFactory:
    """Create and manage isolated Python virtual environments.

    Uses `uv` for fast venv creation when available (10-100x faster
    than stdlib venv). Falls back to stdlib venv.EnvBuilder.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._use_uv = shutil.which("uv") is not None

    def create(
        self,
        name: str,
        requirements: tuple[str, ...] = (),
    ) -> Path:
        """Create a venv and optionally install requirements.

        Returns the path to the venv root directory.
        """
        venv_path = self._base_dir / name

        if self._use_uv:
            self._create_with_uv(venv_path, requirements)
        else:
            self._create_with_stdlib(venv_path, requirements)

        return venv_path

    def destroy(self, name: str) -> None:
        """Remove a venv completely."""
        venv_path = self._base_dir / name
        if venv_path.exists():
            shutil.rmtree(venv_path)

    def python_path(self, venv_path: Path) -> Path:
        """Get the Python interpreter path for a venv."""
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    def _create_with_uv(
        self, venv_path: Path, requirements: tuple[str, ...]
    ) -> None:
        subprocess.run(
            ["uv", "venv", str(venv_path), "--seed"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        if requirements:
            subprocess.run(
                ["uv", "pip", "install", "--python", str(self.python_path(venv_path)),
                 *requirements],
                check=True,
                capture_output=True,
                timeout=120,
            )

    def _create_with_stdlib(
        self, venv_path: Path, requirements: tuple[str, ...]
    ) -> None:
        builder = venv.EnvBuilder(
            system_site_packages=False,
            clear=True,
            with_pip=True,
        )
        builder.create(str(venv_path))
        if requirements:
            pip = self._pip_path(venv_path)
            subprocess.run(
                [str(pip), "install", "--quiet", *requirements],
                check=True,
                capture_output=True,
                timeout=120,
            )

    def _pip_path(self, venv_path: Path) -> Path:
        if sys.platform == "win32":
            return venv_path / "Scripts" / "pip.exe"
        return venv_path / "bin" / "pip"
```

### 6.2 Warm Pool Extension (Future)

For NFR-02's ≤1s warm-pool target, the factory can maintain a pool of pre-created venvs:

```python
@dataclass
class VenvPool:
    """Pre-warmed venv pool for fast sandbox creation.

    Maintains N idle venvs with a base set of packages.
    When a sandbox requests a venv, the pool hands off an idle
    one and starts creating a replacement in the background.
    """
    pool_size: int = 3
    base_requirements: tuple[str, ...] = ()
    _idle: list[Path] = field(default_factory=list)
    _factory: VenvFactory = field(init=False)
```

This is a post-MVP optimization. For MVP, cold creation via `uv` (~1–3s) is acceptable.

---

## 7. Result Capture

### 7.1 ExecutionResult Lifecycle

```
Script runs in subprocess
         │
         ▼
┌─────────────────────┐
│  stdout (captured)   │──→ UTF-8 decode ──→ ExecutionResult.stdout
│  stderr (captured)   │──→ UTF-8 decode ──→ ExecutionResult.stderr
│  exit_code (int)     │──→ directly      ──→ ExecutionResult.exit_code
│  wall-clock time     │──→ monotonic()   ──→ ExecutionResult.duration_ms
│  timeout flag        │──→ from except   ──→ ExecutionResult.timed_out
│  memory flag         │──→ from except   ──→ ExecutionResult.memory_exceeded
└─────────────────────┘
         │
         ▼
    fingerprint = SHA-256(exit_code ∥ stdout ∥ stderr)
```

### 7.2 Structured Output Protocol

For tasks that produce structured results (JSON), the sandbox supports a convention: if the script writes a file named `_nines_output.json` in the working directory, the `SandboxManager` reads and returns it as parsed data.

```python
@dataclass(frozen=True)
class RichExecutionResult(ExecutionResult):
    """Extended result with optional structured output."""
    structured_output: dict[str, Any] | None = None


def _collect_structured_output(workspace: Path) -> dict[str, Any] | None:
    output_path = workspace / "_nines_output.json"
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    return None
```

---

## 8. Determinism and Seed Control

Determinism is critical for reliable evaluation (NFR-11, NFR-12). The sandbox controls randomness at multiple levels from a single master seed.

### 8.1 Seed Propagation

```
Master Seed (from CLI --seed or NinesConfig)
    │
    ├──→ PYTHONHASHSEED=<seed>          (stdlib hash determinism)
    ├──→ NINES_SEED=<seed>              (application-level seed)
    ├──→ random.seed(<seed>)            (stdlib random)
    ├──→ numpy.random.seed(<seed>)      (if numpy present)
    └──→ torch.manual_seed(<seed>)      (if torch present)
```

### 8.2 Environment Variables

```python
def _build_sandbox_env(config: SandboxConfig) -> dict[str, str]:
    """Build the environment variable dict for a sandbox subprocess."""
    env: dict[str, str] = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if config.seed is not None:
        env["PYTHONHASHSEED"] = str(config.seed)
        env["NINES_SEED"] = str(config.seed)
        env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        env["TF_DETERMINISTIC_OPS"] = "1"
    else:
        env["PYTHONHASHSEED"] = "0"

    env.update(config.env_overrides)
    return env
```

### 8.3 Seed Initialization Snippet

When a seed is configured, the `SandboxManager` prepends this snippet to every executed script:

```python
def _seed_init_snippet(seed: int) -> str:
    """Python code prepended to evaluation scripts for seed control."""
    return f'''\
import os as _os
import random as _random

_NINES_SEED = int(_os.environ.get("NINES_SEED", {seed}))
_random.seed(_NINES_SEED)

try:
    import numpy as _np
    _np.random.seed(_NINES_SEED)
except ImportError:
    pass

try:
    import torch as _torch
    _torch.manual_seed(_NINES_SEED)
    if _torch.cuda.is_available():
        _torch.cuda.manual_seed_all(_NINES_SEED)
    _torch.backends.cudnn.deterministic = True
    _torch.backends.cudnn.benchmark = False
except ImportError:
    pass

del _os, _random
'''
```

### 8.4 Fingerprint-Based Determinism Verification

To verify determinism, the evaluator compares `ExecutionResult.fingerprint` across multiple runs with the same seed. If fingerprints diverge, the task is flagged as non-deterministic (see §10).

---

## 9. Pollution Detection

Pollution detection verifies that sandbox execution did not modify the host environment (NFR-09). It uses a before/after snapshot diff strategy.

### 9.1 EnvironmentSnapshot

```python
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Immutable snapshot of observable host state."""
    env_vars: dict[str, str]
    watched_file_hashes: dict[str, str]
    watched_dir_listings: dict[str, tuple[str, ...]]
    python_path: tuple[str, ...]
    cwd: str
```

### 9.2 PollutionReport

```python
@dataclass(frozen=True)
class PollutionReport:
    """Result of comparing two environment snapshots."""
    clean: bool
    env_var_changes: tuple[str, ...]
    file_changes: tuple[str, ...]
    dir_changes: tuple[str, ...]
    path_changes: tuple[str, ...]

    @property
    def total_changes(self) -> int:
        return (
            len(self.env_var_changes)
            + len(self.file_changes)
            + len(self.dir_changes)
            + len(self.path_changes)
        )
```

### 9.3 PollutionDetector

```python
class PollutionDetector:
    """Detect host environment changes caused by sandbox execution.

    Takes before/after snapshots and diffs them across four dimensions:
    environment variables, watched files, watched directories, and sys.path.
    """

    def __init__(
        self,
        watched_dirs: list[Path] | None = None,
        watched_files: list[Path] | None = None,
    ) -> None:
        self._watched_dirs = watched_dirs or []
        self._watched_files = watched_files or []

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

    def compare(
        self,
        before: EnvironmentSnapshot,
        after: EnvironmentSnapshot,
    ) -> PollutionReport:
        """Compare two snapshots to detect host environment changes."""
        env_changes = self._diff_dicts(before.env_vars, after.env_vars, "env")
        file_changes = self._diff_dicts(
            before.watched_file_hashes, after.watched_file_hashes, "file"
        )
        dir_changes = self._diff_dir_listings(
            before.watched_dir_listings, after.watched_dir_listings
        )
        path_changes = self._diff_sequences(
            before.python_path, after.python_path, "sys.path"
        )

        return PollutionReport(
            clean=not (env_changes or file_changes or dir_changes or path_changes),
            env_var_changes=tuple(env_changes),
            file_changes=tuple(file_changes),
            dir_changes=tuple(dir_changes),
            path_changes=tuple(path_changes),
        )

    @staticmethod
    def _diff_dicts(
        before: dict[str, str], after: dict[str, str], label: str
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
        before: tuple[str, ...], after: tuple[str, ...], label: str
    ) -> list[str]:
        changes: list[str] = []
        added = set(after) - set(before)
        removed = set(before) - set(after)
        if added:
            changes.append(f"{label} ADDED: {sorted(added)}")
        if removed:
            changes.append(f"{label} REMOVED: {sorted(removed)}")
        return changes
```

### 9.4 Integration with EvalRunner

Every evaluation task execution is wrapped with pollution checking:

```
EvalRunner.run_task(task)
  │
  ├─ before = detector.snapshot()
  ├─ result = sandbox.execute(handle, task_script)
  ├─ after = detector.snapshot()
  ├─ report = detector.compare(before, after)
  │
  ├─ if not report.clean:
  │    log.error("Host pollution detected")
  │    event_bus.emit(SANDBOX_POLLUTION, report)
  │
  └─ return (result, report)
```

---

## 10. Multi-Round Convergence

To verify that evaluation results are stable and reproducible, the sandbox supports multi-round execution with statistical convergence checking (FR-411, NFR-11).

### 10.1 StabilityReport

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StabilityReport:
    """Result of multi-round stability testing."""
    total_runs: int
    unique_fingerprints: int
    dominant_fingerprint: str
    dominant_count: int
    is_stable: bool
    stability_ratio: float   # dominant_count / total_runs
    cv: float                 # coefficient of variation (for scored tasks)
    fingerprint_counts: dict[str, int]
```

### 10.2 StabilityChecker

```python
import math
from collections import Counter


class StabilityChecker:
    """Verify result stability across repeated sandbox executions.

    Runs the same task N times and checks that:
    - For binary/deterministic tasks: all fingerprints match (CV=0)
    - For scored tasks: CV ≤ 5% (NFR-11 threshold)
    """

    def __init__(
        self,
        manager: SandboxManager,
        min_rounds: int = 3,
        max_rounds: int = 10,
        cv_threshold: float = 0.05,
    ) -> None:
        self._manager = manager
        self._min_rounds = min_rounds
        self._max_rounds = max_rounds
        self._cv_threshold = cv_threshold

    def check(
        self,
        config: SandboxConfig,
        script: str,
        extract_score: callable | None = None,
    ) -> StabilityReport:
        """Run multi-round stability test.

        Args:
            config: Sandbox configuration (should include a fixed seed).
            script: The evaluation script to run repeatedly.
            extract_score: Optional callable that extracts a numeric score
                from ExecutionResult. Used for CV calculation on scored tasks.
        """
        fingerprints: list[str] = []
        scores: list[float] = []

        for i in range(self._max_rounds):
            handle = self._manager.create(config)
            try:
                result = self._manager.execute(handle, script)
                fingerprints.append(result.fingerprint)
                if extract_score is not None:
                    scores.append(extract_score(result))
            finally:
                self._manager.destroy(handle.id)

            if i + 1 >= self._min_rounds:
                if self._can_stop_early(fingerprints, scores):
                    break

        counts = Counter(fingerprints)
        dominant_fp, dominant_count = counts.most_common(1)[0]
        cv = _coefficient_of_variation(scores) if scores else 0.0

        return StabilityReport(
            total_runs=len(fingerprints),
            unique_fingerprints=len(counts),
            dominant_fingerprint=dominant_fp,
            dominant_count=dominant_count,
            is_stable=(
                dominant_count == len(fingerprints)
                if not scores
                else cv <= self._cv_threshold
            ),
            stability_ratio=dominant_count / len(fingerprints),
            cv=cv,
            fingerprint_counts=dict(counts),
        )

    def _can_stop_early(
        self, fingerprints: list[str], scores: list[float]
    ) -> bool:
        counts = Counter(fingerprints)
        if len(counts) == 1:
            return True  # perfectly stable
        if scores and len(scores) >= self._min_rounds:
            cv = _coefficient_of_variation(scores)
            if cv <= self._cv_threshold * 0.5:
                return True  # well within threshold
        return False


def _coefficient_of_variation(values: list[float]) -> float:
    """Compute CV = stddev / mean. Returns 0.0 for empty or zero-mean data."""
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    if mean == 0.0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / n
    return math.sqrt(variance) / abs(mean)
```

### 10.3 Convergence Criteria

| Task Type | Stability Criterion | Threshold |
|-----------|-------------------|-----------|
| Deterministic (no randomness) | All fingerprints identical | CV = 0.0 |
| Scored with seed | Coefficient of variation | CV ≤ 0.05 (5%) |
| Binary pass/fail | All rounds agree | 3/3 match |

For tasks using FR-110 Pass³ metric, the multi-round check runs exactly 3 times and requires all 3 to pass — this is the "all-3-must-pass" consistency metric.

---

## 11. Lifecycle and Resource Management

### 11.1 Sandbox State Machine

```
                create()
INITIAL ─────────────────→ READY
                             │
                   execute() │ (repeatable)
                             ▼
                           RUNNING ──→ COMPLETED
                             │              │
                        timeout/error       │
                             ▼              │
                           FAILED           │
                             │              │
                    destroy() │    destroy() │
                             ▼              ▼
                          DESTROYED ◄───────┘
```

### 11.2 Cleanup Guarantees

The `SandboxManager` implements defense-in-depth cleanup:

1. **Explicit**: `destroy(sandbox_id)` or `destroy_all()`
2. **Context manager**: `sandbox_scope()` guarantees cleanup on exit
3. **atexit hook**: `SandboxManager` registers `destroy_all` with `atexit` for crash recovery
4. **tmpdir prefix**: All sandboxes use the `nines_sandbox_` prefix, enabling external cleanup scripts

```python
import atexit


class SandboxManager:
    def __init__(self, ...) -> None:
        ...
        atexit.register(self.destroy_all)
```

### 11.3 Resource Limits Summary

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| Wall-clock time | Configurable (default 30s) | `subprocess.run(timeout=...)` |
| Virtual memory | Configurable (default 512MB) | `resource.setrlimit(RLIMIT_AS, ...)` |
| Disk space | tmpdir only (OS-managed) | `shutil.rmtree` on cleanup |
| Process count | Single process group | `start_new_session=True` + SIGKILL on timeout |
| Network | Blocked by default via proxy env vars (`sandbox.allow_network = false`); configurable | Full isolation: future netns or seccomp |
| CPU | No restriction (MVP) | Future: cgroups |

---

## 12. Configuration

Sandbox settings are part of the `NinesConfig` hierarchy under the `[sandbox]` section:

```toml
[sandbox]
default_timeout = 30
default_memory_mb = 512
isolation = "full"           # "none", "process", "venv", "full"
keep_on_failure = false
base_dir = ""                # empty = system tempdir
allow_network = false        # block HTTP clients via proxy env vars (M-05)

[sandbox.determinism]
default_seed = 42
verify_determinism = true
stability_rounds = 3
cv_threshold = 0.05

[sandbox.pollution]
enabled = true
watched_dirs = []
watched_files = []
```

### Mapping to SandboxConfig

```python
def sandbox_config_from_nines_config(
    nines_config: NinesConfig,
    overrides: dict[str, Any] | None = None,
) -> SandboxConfig:
    """Build a SandboxConfig from the global NinesConfig and optional overrides."""
    cfg = nines_config.sandbox
    base = SandboxConfig(
        timeout_seconds=cfg.default_timeout,
        max_memory_mb=cfg.default_memory_mb,
        isolation=IsolationLevel(cfg.isolation),
        keep_on_failure=cfg.keep_on_failure,
        seed=cfg.determinism.default_seed if cfg.determinism.verify_determinism else None,
    )
    if overrides:
        from dataclasses import replace
        base = replace(base, **overrides)
    return base
```

---

## 13. Requirement Traceability

| Requirement | Section | How Addressed |
|-------------|---------|---------------|
| **NFR-02** Sandbox overhead ≤5s cold, ≤1s warm | §6 VenvFactory | `uv` for fast creation; warm pool extension for ≤1s |
| **NFR-09** No host pollution | §2, §9 | Three-layer isolation + before/after snapshot diff |
| **NFR-10** No cross-sandbox pollution | §4 SandboxManager | Each sandbox gets unique ID, workspace, and venv |
| **NFR-11** Determinism CV ≤5% | §8, §10 | Seed propagation + multi-round stability checking |
| **NFR-12** Seed control coverage | §8 | Single master seed → PYTHONHASHSEED + NINES_SEED + per-framework seeds |
| **FR-114** Eval orchestration | §4, §5 | SandboxManager integrates with EvalRunner pipeline |
| **FR-116** Collateral damage detection | §9 PollutionDetector | Before/after diff across env, files, dirs, sys.path |
| **FR-411** Multi-round stability | §10 StabilityChecker | N-round execution with CV and fingerprint comparison |
| **CON-05** No Docker for MVP | §2 | Pure stdlib + uv: subprocess, venv, tempfile |
| **CON-09** Protocol-based interfaces | §3 | All components defined as Protocol classes |

---

*Last modified: 2026-04-11*
