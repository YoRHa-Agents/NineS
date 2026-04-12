"""NineS Sandbox — lightweight, Docker-free isolated execution.

Public re-exports for consumers::

    from nines.sandbox import (
        SandboxManager,
        SandboxConfig,
        SandboxContext,
        IsolatedRunner,
        RunResult,
        VenvFactory,
        PollutionDetector,
        PollutionReport,
        EnvironmentSnapshot,
    )
"""

from nines.sandbox.isolation import (
    EnvironmentSnapshot,
    PollutionDetector,
    PollutionReport,
    VenvFactory,
)
from nines.sandbox.manager import (
    SandboxConfig,
    SandboxContext,
    SandboxManager,
)
from nines.sandbox.runner import (
    IsolatedRunner,
    RunResult,
)

__all__ = [
    "EnvironmentSnapshot",
    "IsolatedRunner",
    "PollutionDetector",
    "PollutionReport",
    "RunResult",
    "SandboxConfig",
    "SandboxContext",
    "SandboxManager",
    "VenvFactory",
]
