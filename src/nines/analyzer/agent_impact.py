"""Agent impact analysis for AI-oriented repositories.

Analyzes how a repository influences AI Agent effectiveness through
mechanism decomposition, context economics estimation, and
Agent-facing artifact detection.

Covers: FR-313.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nines.core.identity import format_finding_id, project_fingerprint
from nines.core.models import Finding, KnowledgeUnit

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".eggs", "*.egg-info",
})


@dataclass
class AgentMechanism:
    """A discrete mechanism through which a repo influences Agent behavior.

    Attributes
    ----------
    id:
        Unique mechanism identifier.
    name:
        Human-readable name for the mechanism.
    category:
        Classification bucket — one of ``"context_compression"``,
        ``"behavioral_instruction"``, ``"tool_management"``,
        ``"safety"``, or ``"distribution"``.
    description:
        What the mechanism does and how it affects Agent behavior.
    evidence_files:
        Filesystem paths that contribute evidence for this mechanism.
    estimated_token_impact:
        Positive means the mechanism *adds* tokens to Agent context,
        negative means it *saves* tokens.
    confidence:
        Confidence score in ``[0.0, 1.0]``.
    """

    id: str
    name: str
    category: str
    description: str
    evidence_files: list[str] = field(default_factory=list)
    estimated_token_impact: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "evidence_files": list(self.evidence_files),
            "estimated_token_impact": self.estimated_token_impact,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMechanism:
        """Deserialize from a plain dictionary."""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            category=data.get("category", ""),
            description=data.get("description", ""),
            evidence_files=list(data.get("evidence_files", [])),
            estimated_token_impact=data.get("estimated_token_impact", 0),
            confidence=data.get("confidence", 0.0),
        )


@dataclass
class ContextEconomics:
    """Token budget analysis for an AI-oriented repository.

    Attributes
    ----------
    overhead_tokens:
        Tokens the tool adds to every Agent interaction.
    estimated_savings_ratio:
        Estimated ratio of output tokens saved per interaction.
    mechanism_count:
        Number of distinct Agent-influence mechanisms detected.
    agent_facing_files:
        Count of files designed for Agent consumption.
    total_agent_context_tokens:
        Aggregate token count across all Agent-facing files.
    break_even_interactions:
        Number of interactions needed for net-positive token economics.
    """

    overhead_tokens: int = 0
    estimated_savings_ratio: float = 0.0
    mechanism_count: int = 0
    agent_facing_files: int = 0
    total_agent_context_tokens: int = 0
    break_even_interactions: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "overhead_tokens": self.overhead_tokens,
            "estimated_savings_ratio": self.estimated_savings_ratio,
            "mechanism_count": self.mechanism_count,
            "agent_facing_files": self.agent_facing_files,
            "total_agent_context_tokens": self.total_agent_context_tokens,
            "break_even_interactions": self.break_even_interactions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextEconomics:
        """Deserialize from a plain dictionary."""
        return cls(
            overhead_tokens=data.get("overhead_tokens", 0),
            estimated_savings_ratio=data.get("estimated_savings_ratio", 0.0),
            mechanism_count=data.get("mechanism_count", 0),
            agent_facing_files=data.get("agent_facing_files", 0),
            total_agent_context_tokens=data.get("total_agent_context_tokens", 0),
            break_even_interactions=data.get("break_even_interactions", 0),
        )


@dataclass
class AgentImpactReport:
    """Complete Agent impact analysis report.

    Attributes
    ----------
    target:
        Filesystem path that was analyzed.
    mechanisms:
        Detected Agent-influence mechanisms.
    economics:
        Token budget analysis summary.
    agent_facing_artifacts:
        Paths of files designed for Agent consumption.
    findings:
        Actionable findings about the repo's Agent impact profile.
    knowledge_units:
        Knowledge units representing Agent-impact knowledge.
    """

    target: str
    mechanisms: list[AgentMechanism] = field(default_factory=list)
    economics: ContextEconomics = field(default_factory=ContextEconomics)
    agent_facing_artifacts: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    knowledge_units: list[KnowledgeUnit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "target": self.target,
            "mechanisms": [m.to_dict() for m in self.mechanisms],
            "economics": self.economics.to_dict(),
            "agent_facing_artifacts": list(self.agent_facing_artifacts),
            "findings": [f.to_dict() for f in self.findings],
            "knowledge_units": [ku.to_dict() for ku in self.knowledge_units],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentImpactReport:
        """Deserialize from a plain dictionary."""
        return cls(
            target=data["target"],
            mechanisms=[
                AgentMechanism.from_dict(m)
                for m in data.get("mechanisms", [])
            ],
            economics=ContextEconomics.from_dict(data.get("economics", {})),
            agent_facing_artifacts=list(
                data.get("agent_facing_artifacts", [])
            ),
            findings=[
                Finding.from_dict(f) for f in data.get("findings", [])
            ],
            knowledge_units=[
                KnowledgeUnit.from_dict(ku)
                for ku in data.get("knowledge_units", [])
            ],
        )


class AgentImpactAnalyzer:
    """Analyzes repositories for their impact on AI Agent effectiveness.

    Unlike traditional code analysis which focuses on complexity, coupling,
    and architectural patterns, this analyzer identifies:

    1. Agent-facing artifacts (skills, rules, prompts, AGENTS.md, etc.)
    2. Mechanisms that influence Agent behavior (compression, instruction, safety)
    3. Context economics (token overhead vs savings)
    4. Distribution patterns (how the repo reaches multiple Agent platforms)
    """

    AGENT_ARTIFACT_PATTERNS = [
        r"CLAUDE\.md$", r"\.claude/", r"SKILL\.md$", r"\.skill$",
        r"\.cursor/rules/", r"\.cursorrules$",
        r"\.windsurf/rules/",
        r"\.clinerules/",
        r"copilot-instructions\.md$", r"AGENTS\.md$",
        r"\.codex/", r"codex-plugin/",
        r"CONTEXT\.md$", r"SYSTEM_PROMPT",
        r"pyproject\.toml$",
        r"\.github/copilot/",
        r"\.aider",
        r"RULES\.md$",
    ]

    COMPRESSION_INDICATORS = [
        "compress", "token", "shorten", "strip", "minif", "compact",
        "terse", "concise", "abbreviat", "reduc",
    ]

    SAFETY_INDICATORS = [
        "safety", "security", "irreversible", "danger", "warning",
        "auto-clarity", "fallback", "restore", "backup",
    ]

    BEHAVIORAL_INDICATORS = [
        "instruction", "rule", "prompt", "convention", "must", "always",
        "never", "should", "style", "guideline",
    ]

    DISTRIBUTION_INDICATORS = [
        "sync", "deploy", "publish", "ci", "workflow", "multi-agent",
        "distribute", "platform", "cross-ide",
    ]

    PERSISTENCE_INDICATORS = [
        "drift", "enforce", "persist", "mode", "lock", "guard",
        "invariant", "constraint", "assert",
    ]

    _TOKENS_PER_WORD = 1.3

    def __init__(self, project_id: str | None = None) -> None:
        """Initialize agent impact analyzer.

        Parameters
        ----------
        project_id:
            Optional pre-computed project fingerprint.  When ``None``,
            :meth:`analyze` computes one from the target path.
        """
        self._agent_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.AGENT_ARTIFACT_PATTERNS
        ]
        self._project_id: str | None = project_id

    def analyze(self, path: str | Path) -> AgentImpactReport:
        """Run full Agent impact analysis on a repository.

        Parameters
        ----------
        path:
            Root directory (or single file) to analyze.

        Returns
        -------
        AgentImpactReport
            Complete analysis report with mechanisms, economics,
            artifacts, findings, and knowledge units.
        """
        target = Path(path)
        logger.info("Starting Agent impact analysis on %s", target)

        # Compute / cache the project fingerprint so all findings emitted by
        # this analyze() call share the same namespace.  See C02.
        active_project_id = self._project_id
        if active_project_id is None:
            try:
                active_project_id = project_fingerprint(target)
            except (OSError, ValueError) as exc:
                logger.warning(
                    "Could not compute project fingerprint for %s: %s; "
                    "emitting legacy unscoped IDs",
                    target, exc,
                )
                active_project_id = None

        artifacts = self._discover_agent_artifacts(target)
        logger.debug("Discovered %d Agent-facing artifacts", len(artifacts))

        economics = self._estimate_context_economics(target, artifacts)
        mechanisms = self._detect_mechanisms(target, artifacts)

        economics.mechanism_count = len(mechanisms)
        total_mechanism_tokens = sum(
            abs(m.estimated_token_impact) for m in mechanisms
        )
        if total_mechanism_tokens > 0:
            economics.total_agent_context_tokens += total_mechanism_tokens
            economics.overhead_tokens += total_mechanism_tokens

        if economics.overhead_tokens == 0 and artifacts:
            min_estimate = len(artifacts) * 50
            economics.overhead_tokens = min_estimate
            economics.total_agent_context_tokens = max(
                economics.total_agent_context_tokens, min_estimate,
            )

        findings = self._generate_findings(
            mechanisms, economics, artifacts, project_id=active_project_id,
        )
        units = self._create_knowledge_units(mechanisms, artifacts)

        logger.info(
            "Agent impact analysis complete: %d mechanisms, %d artifacts, "
            "%d findings",
            len(mechanisms), len(artifacts), len(findings),
        )

        return AgentImpactReport(
            target=str(target),
            mechanisms=mechanisms,
            economics=economics,
            agent_facing_artifacts=artifacts,
            findings=findings,
            knowledge_units=units,
        )

    def _discover_agent_artifacts(self, target: Path) -> list[str]:
        """Find all files designed for Agent consumption.

        Recursively walks ``target`` (skipping common non-source
        directories) and tests each path against
        :attr:`AGENT_ARTIFACT_PATTERNS`.

        Parameters
        ----------
        target:
            Root directory or single file to scan.

        Returns
        -------
        list[str]
            Sorted list of relative path strings for matched files.
        """
        if target.is_file():
            posix = target.as_posix()
            if any(pat.search(posix) for pat in self._agent_patterns):
                return [str(target)]
            return []

        if not target.is_dir():
            logger.warning("Target is neither file nor directory: %s", target)
            return []

        artifacts: list[str] = []
        for item in sorted(target.rglob("*")):
            if self._should_skip(item):
                continue
            if not item.is_file():
                continue
            relative = item.relative_to(target).as_posix()
            if any(pat.search(relative) for pat in self._agent_patterns):
                artifacts.append(relative)
        return sorted(artifacts)

    def _estimate_context_economics(
        self, target: Path, artifacts: list[str],
    ) -> ContextEconomics:
        """Estimate the token economics of the repository's Agent-facing content.

        Uses a simple word-based approximation (words * 1.3 ~ tokens) for
        estimation without requiring tiktoken dependency.

        Parameters
        ----------
        target:
            Root directory of the repository.
        artifacts:
            Relative paths of Agent-facing files.

        Returns
        -------
        ContextEconomics
            Token budget analysis for the Agent-facing content.
        """
        total_tokens = 0
        for rel_path in artifacts:
            content = self._read_file_safe(target / rel_path)
            total_tokens += self._estimate_tokens(content)

        overhead = total_tokens
        savings_ratio = min(0.95, len(artifacts) * 0.05) if artifacts else 0.0

        if savings_ratio > 0 and overhead > 0:
            saved_per_interaction = int(overhead * savings_ratio)
            break_even = (
                max(1, (overhead + saved_per_interaction - 1) // saved_per_interaction)
                if saved_per_interaction > 0 else 0
            )
        else:
            break_even = 0

        return ContextEconomics(
            overhead_tokens=overhead,
            estimated_savings_ratio=round(savings_ratio, 3),
            mechanism_count=0,
            agent_facing_files=len(artifacts),
            total_agent_context_tokens=total_tokens,
            break_even_interactions=break_even,
        )

    def _detect_mechanisms(
        self, target: Path, artifacts: list[str],
    ) -> list[AgentMechanism]:
        """Identify discrete mechanisms that influence Agent behavior.

        Reads each Agent-facing file and classifies detected patterns into
        mechanism categories: behavioral instruction, context compression,
        safety, distribution, and persistence.

        Parameters
        ----------
        target:
            Root directory of the repository.
        artifacts:
            Relative paths of Agent-facing files.

        Returns
        -------
        list[AgentMechanism]
            All detected mechanisms, sorted by category then name.
        """
        mechanisms: list[AgentMechanism] = []
        category_evidence: dict[str, dict[str, list[str]]] = {}

        for rel_path in artifacts:
            content = self._read_file_safe(target / rel_path).lower()
            if not content:
                continue

            self._collect_mechanism_evidence(
                rel_path, content, category_evidence,
            )

        for category, sub_mechs in sorted(category_evidence.items()):
            for name, files in sorted(sub_mechs.items()):
                total_content = ""
                for f in files:
                    total_content += self._read_file_safe(target / f) + " "
                token_impact = self._estimate_tokens(total_content)
                if category == "context_compression":
                    token_impact = -token_impact

                confidence = min(1.0, len(files) * 0.3 + 0.1)
                mechanisms.append(AgentMechanism(
                    id=f"mech-{uuid.uuid4().hex[:8]}",
                    name=name,
                    category=category,
                    description=self._describe_mechanism(category, name, files),
                    evidence_files=sorted(files),
                    estimated_token_impact=token_impact,
                    confidence=round(confidence, 2),
                ))

        return mechanisms

    def _collect_mechanism_evidence(
        self,
        rel_path: str,
        content: str,
        evidence: dict[str, dict[str, list[str]]],
    ) -> None:
        """Scan content of a single file for mechanism indicators.

        Populates ``evidence`` mapping of
        ``{category: {mechanism_name: [file_paths]}}``.

        Parameters
        ----------
        rel_path:
            Relative path of the file being scanned.
        content:
            Lowercased file content.
        evidence:
            Accumulator dict mutated in place.
        """
        checks: list[tuple[str, str, list[str]]] = [
            ("behavioral_instruction", "behavioral_rules", self.BEHAVIORAL_INDICATORS),
            ("context_compression", "token_compression", self.COMPRESSION_INDICATORS),
            ("safety", "safety_guardrails", self.SAFETY_INDICATORS),
            ("distribution", "multi_platform_sync", self.DISTRIBUTION_INDICATORS),
            ("persistence", "drift_prevention", self.PERSISTENCE_INDICATORS),
        ]

        for category, mech_name, indicators in checks:
            if any(ind in content for ind in indicators):
                bucket = evidence.setdefault(category, {})
                bucket.setdefault(mech_name, [])
                if rel_path not in bucket[mech_name]:
                    bucket[mech_name].append(rel_path)

    def _describe_mechanism(
        self, category: str, name: str, files: list[str],
    ) -> str:
        """Generate a human-readable description for a mechanism.

        Parameters
        ----------
        category:
            Mechanism category slug.
        name:
            Mechanism name slug.
        files:
            Evidence file paths.

        Returns
        -------
        str
            Descriptive sentence for the mechanism.
        """
        descriptions: dict[str, str] = {
            "behavioral_instruction": (
                "Provides behavioral rules and conventions that shape "
                "Agent output style and decision-making"
            ),
            "context_compression": (
                "Reduces token usage through compression, abbreviation, "
                "or compact representation strategies"
            ),
            "safety": (
                "Implements safety guardrails such as confirmation prompts, "
                "auto-clarity checks, or irreversible-action protections"
            ),
            "distribution": (
                "Distributes Agent configuration across multiple platforms "
                "or synchronizes rules between IDE integrations"
            ),
            "persistence": (
                "Enforces behavioral persistence through drift prevention, "
                "mode locking, or invariant enforcement"
            ),
        }
        base = descriptions.get(category, f"Mechanism '{name}' in category '{category}'")
        return f"{base} (evidence from {len(files)} file(s))"

    def _generate_findings(
        self,
        mechanisms: list[AgentMechanism],
        economics: ContextEconomics,
        artifacts: list[str],
        project_id: str | None = None,
    ) -> list[Finding]:
        """Generate findings about Agent impact characteristics.

        Produces actionable findings covering artifact counts,
        mechanism coverage, token economics, and coverage gaps.

        Parameters
        ----------
        mechanisms:
            Detected Agent mechanisms.
        economics:
            Token economics analysis.
        artifacts:
            Agent-facing artifact paths.

        Returns
        -------
        list[Finding]
            Ordered list of findings.
        """
        findings: list[Finding] = []
        idx = 0

        findings.append(Finding(
            id=format_finding_id("AI", idx, project_id),
            severity="info",
            category="agent_impact",
            message=(
                f"Repository contains {len(artifacts)} Agent-facing "
                f"artifact(s) across {len(mechanisms)} mechanism(s)"
            ),
            location=economics.agent_facing_files and artifacts[0] or "",
        ))
        idx += 1

        if economics.total_agent_context_tokens > 0:
            findings.append(Finding(
                id=format_finding_id("AI", idx, project_id),
                severity="info",
                category="context_economics",
                message=(
                    f"Total Agent context: ~{economics.total_agent_context_tokens} tokens, "
                    f"overhead: ~{economics.overhead_tokens} tokens, "
                    f"estimated savings ratio: {economics.estimated_savings_ratio:.1%}"
                ),
                location="",
            ))
            idx += 1

        if economics.overhead_tokens > 5000:
            findings.append(Finding(
                id=format_finding_id("AI", idx, project_id),
                severity="warning",
                category="context_economics",
                message=(
                    f"Agent context overhead is high ({economics.overhead_tokens} tokens). "
                    f"Consider compressing or splitting Agent-facing files."
                ),
                location="",
                suggestion=(
                    "Split large instruction files into role-specific segments "
                    "or apply token-compression techniques."
                ),
            ))
            idx += 1

        categories_present = {m.category for m in mechanisms}
        all_categories = {
            "behavioral_instruction", "context_compression",
            "safety", "distribution", "persistence",
        }
        missing = all_categories - categories_present
        if missing and artifacts:
            findings.append(Finding(
                id=format_finding_id("AI", idx, project_id),
                severity="info",
                category="coverage_gap",
                message=(
                    f"No mechanisms detected for: {', '.join(sorted(missing))}. "
                    f"Consider adding support for these areas."
                ),
                location="",
                suggestion=(
                    "Review whether the repository would benefit from "
                    "mechanisms in the missing categories."
                ),
            ))
            idx += 1

        if not artifacts:
            findings.append(Finding(
                id=format_finding_id("AI", idx, project_id),
                severity="info",
                category="agent_impact",
                message=(
                    "No Agent-facing artifacts detected. This repository "
                    "does not appear to target AI Agent integration."
                ),
                location="",
            ))
            idx += 1

        for mech in mechanisms:
            if mech.confidence < 0.3:
                findings.append(Finding(
                    id=format_finding_id("AI", idx, project_id),
                    severity="info",
                    category="low_confidence",
                    message=(
                        f"Mechanism '{mech.name}' ({mech.category}) has low "
                        f"confidence ({mech.confidence:.0%}). Evidence may be "
                        f"circumstantial."
                    ),
                    location=mech.evidence_files[0] if mech.evidence_files else "",
                ))
                idx += 1

        return findings

    def _create_knowledge_units(
        self,
        mechanisms: list[AgentMechanism],
        artifacts: list[str],
    ) -> list[KnowledgeUnit]:
        """Create knowledge units representing Agent-impact knowledge.

        One unit per mechanism plus one summary unit for the overall
        Agent impact profile.

        Parameters
        ----------
        mechanisms:
            Detected mechanisms.
        artifacts:
            Agent-facing artifact paths.

        Returns
        -------
        list[KnowledgeUnit]
            Knowledge units suitable for downstream pattern detection.
        """
        units: list[KnowledgeUnit] = []

        for mech in mechanisms:
            units.append(KnowledgeUnit(
                id=f"agent_mech::{mech.id}",
                source=mech.evidence_files[0] if mech.evidence_files else "",
                content=f"{mech.name}: {mech.description}",
                unit_type="agent_mechanism",
                relationships={
                    "evidence_files": mech.evidence_files,
                    "category": mech.category,
                },
                metadata={
                    "category": mech.category,
                    "confidence": str(mech.confidence),
                    "token_impact": str(mech.estimated_token_impact),
                },
            ))

        if mechanisms or artifacts:
            units.append(KnowledgeUnit(
                id="agent_impact::summary",
                source="",
                content=(
                    f"Agent impact profile: {len(mechanisms)} mechanism(s), "
                    f"{len(artifacts)} artifact(s)"
                ),
                unit_type="agent_impact_summary",
                relationships={
                    "mechanisms": [f"agent_mech::{m.id}" for m in mechanisms],
                    "artifacts": artifacts,
                },
                metadata={
                    "mechanism_count": str(len(mechanisms)),
                    "artifact_count": str(len(artifacts)),
                },
            ))

        return units

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: word_count * 1.3.

        Parameters
        ----------
        text:
            Input text to estimate tokens for.

        Returns
        -------
        int
            Estimated token count (always >= 0).
        """
        if not text:
            return 0
        word_count = len(text.split())
        return int(word_count * AgentImpactAnalyzer._TOKENS_PER_WORD)

    @staticmethod
    def _read_file_safe(path: Path) -> str:
        """Read file content, returning empty string on failure.

        Handles encoding errors, permission errors, and other I/O
        issues gracefully.

        Parameters
        ----------
        path:
            Filesystem path to read.

        Returns
        -------
        str
            File content, or ``""`` if the file cannot be read.
        """
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError) as exc:
            logger.debug("Could not read %s: %s", path, exc)
            return ""

    @staticmethod
    def _should_skip(path: Path) -> bool:
        """Check whether a path should be skipped during directory traversal.

        Parameters
        ----------
        path:
            Path to check against the skip list.

        Returns
        -------
        bool
            ``True`` if any path component matches a skip directory name.
        """
        return any(part in _SKIP_DIRS for part in path.parts)
