"""Error type hierarchy for NineS.

All NineS-specific exceptions derive from :class:`NinesError`, enabling
uniform ``except NinesError`` handling while preserving fine-grained
catch granularity for callers that need it.

Every error carries a human-readable *message*, a structured *details*
dict for programmatic consumption, and an optional *cause* for exception
chaining.

Covers: NFR-20 (error hierarchy), NFR-21 (no silent failures), FR-509.
"""

from __future__ import annotations

from typing import Any


class NinesError(Exception):
    """Base exception for all NineS operations.

    Parameters
    ----------
    message:
        Human-readable error summary.
    details:
        Machine-readable context (error codes, field names, etc.).
    cause:
        Optional chained exception that triggered this error.
    """

    def __init__(
        self,
        message: str = "",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize nines error."""
        self.message = message
        self.details: dict[str, Any] = details or {}
        self.cause = cause
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


class EvalError(NinesError):
    """Raised when the evaluation pipeline encounters a failure.

    Covers task loading, execution, scoring, and reporting errors
    that occur within the ``eval/`` module.
    """


class CollectorError(NinesError):
    """Raised when an information collection operation fails.

    Covers source discovery, API communication, storage, and
    tracking errors within the ``collector/`` module.
    """


class AnalyzerError(NinesError):
    """Raised when code analysis encounters a failure.

    Covers AST parsing, structural analysis, decomposition, and
    knowledge indexing errors within the ``analyzer/`` module.
    """


class SandboxError(NinesError):
    """Raised when sandbox isolation encounters a failure.

    Covers sandbox creation, timeout, pollution detection, and
    resource limit violations within the ``sandbox/`` module.
    """


class ConfigError(NinesError):
    """Raised when configuration loading or validation fails.

    Covers missing config files, TOML parse errors, and value
    constraint violations.
    """


class ConfigFileNotFoundError(ConfigError):
    """TOML config file not found at expected path."""


class ConfigParseError(ConfigError):
    """TOML syntax error in a config file."""


class ConfigValidationError(ConfigError):
    """Value constraint violation in configuration."""


class SkillError(NinesError):
    """Raised when skill generation or installation fails.

    Covers manifest generation, adapter emission, and installation
    errors within the ``skill/`` module.
    """


class OrchestrationError(NinesError):
    """Raised when workflow orchestration or cross-module coordination fails.

    Covers workflow engine errors, stage scheduling failures, and
    artifact passing issues within the ``orchestrator/`` module.
    """
