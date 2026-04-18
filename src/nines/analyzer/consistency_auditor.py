"""Cross-artifact consistency auditor for NineS analyzer reports.

C10 (revised POC plan).  After Wave 1 fixed the §4.1 / §4.5 / §4.6
defects at the source (C03 / C02 / C09 respectively), C10's mission
shifts from "detect today's known bugs" to "enforce invariants so a
future PR cannot silently re-introduce them".  The auditor is a pure
read-only consumer of analyzer JSON; it never mutates state.

Two execution modes are wired into ``nines analyze``:

* Advisory (``--audit``, default): findings are printed and embedded
  in the JSON output, but the command always exits ``0``.
* Strict (``--audit --strict-audit``): the command exits non-zero
  when at least one ``severity="critical"`` finding is produced.

Built-in checks (six, registered by default in
:class:`ConsistencyAuditor`):

1. :class:`FindingIDUniquenessCheck` — duplicate finding IDs (§4.5).
2. :class:`FindingIDNamespaceCheck` — namespaced ID format (C02).
3. :class:`EconomicsFormulaVersionCheck` — ``formula_version >= 2`` (C09).
4. :class:`EconomicsBreakEvenSanityCheck` — ``break_even == 2``
   regression detector (the §4.6 constant-2 bug).
5. :class:`GraphVerificationPassedCheck` — verifier signal honoured (C03).
6. :class:`ReportMetadataPresenceCheck` — schema-versioning block present.

Passing ``expected_schema_version=N`` to the auditor installs the
optional :class:`SchemaVersioningCheck` (the C10
``audit_schema_versioning`` migration hook called for in
``.local/v2.2.0/validate/02_analytical_validation.md``).

Each :class:`AuditCheck` subclass is intentionally compact (≤ 60 LOC)
so that the audit surface stays readable as new invariants are added.

Covers: C10 revised POC plan; satisfies the
``audit_schema_versioning`` recommendation from the §C10 row of
``02_analytical_validation.md``.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditFinding:
    """One issue surfaced by an :class:`AuditCheck`.

    Attributes
    ----------
    check_name:
        Name of the check that produced the finding (matches the
        check's ``name`` class attribute).
    category:
        Coarse classification (e.g. ``"finding_id"``, ``"economics"``,
        ``"knowledge_graph"``, ``"schema_metadata"``).
    severity:
        ``"critical"`` blocks ``--strict-audit``; ``"warn"`` and
        ``"info"`` are advisory only.
    message:
        Human-readable description of the issue.
    affected_keys:
        Dotted JSON paths into the analyzer report that the finding
        references.  Useful for tooling that wants to highlight the
        offending fields in a UI.
    evidence:
        Free-form dict of values copied from the report so reviewers
        don't have to re-derive them.
    """

    check_name: str
    category: str
    severity: Literal["info", "warn", "critical"]
    message: str
    affected_keys: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "check_name": self.check_name,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "affected_keys": list(self.affected_keys),
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class AuditReport:
    """Aggregated output of :meth:`ConsistencyAuditor.audit`.

    Attributes
    ----------
    checks_run:
        Names of every check executed (in registration order).  Useful
        for diffing audit runs across NineS releases.
    findings:
        Combined findings across all checks.
    summary:
        Counts of findings by severity and by category — see
        :meth:`ConsistencyAuditor.summary` for the schema.
    """

    checks_run: list[str]
    findings: list[AuditFinding]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "checks_run": list(self.checks_run),
            "findings": [f.to_dict() for f in self.findings],
            "summary": dict(self.summary),
        }


# ---------------------------------------------------------------------------
# AuditCheck base class
# ---------------------------------------------------------------------------


class AuditCheck(ABC):
    """Abstract base for cross-artifact consistency checks.

    Subclasses set :attr:`name` and :attr:`category` as class
    attributes and implement :meth:`check`.  Each subclass is kept
    compact (≤ 60 LOC) so the audit surface is easy to review.
    """

    #: Unique check identifier (used in :attr:`AuditFinding.check_name`).
    name: str = ""

    #: Coarse classification for :attr:`AuditFinding.category`.
    category: str = ""

    @abstractmethod
    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        """Inspect *report* and return any surfaced issues."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Built-in checks
# ---------------------------------------------------------------------------


# Pattern from ``references/project-identity.md`` §2 / matches
# ``tests/cli/test_analyze.py::_NAMESPACED_ID_RE``.  The 8-hex
# fingerprint slot guarantees cross-project collision resistance per
# the C02 design.
_NAMESPACED_ID_RE = re.compile(r"^[A-Z]+-[0-9a-f]{8}-[0-9]+$")
_LEGACY_ID_RE = re.compile(r"^[A-Z]+-[0-9]+$")


class FindingIDUniquenessCheck(AuditCheck):
    """Asserts every ``findings[*].id`` is unique within the report.

    Reproduces the §4.5 cross-sample collision detector but applied
    intra-report: even within a single project, a duplicate ID
    indicates a deduplication or dispatcher bug.  Severity ``critical``
    because downstream dashboards dedupe on ``id`` and would silently
    drop the colliding rows.
    """

    name = "finding_id_uniqueness"
    category = "finding_id"

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        findings = report.get("findings") or []
        ids: list[str] = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            fid = f.get("id")
            if isinstance(fid, str):
                ids.append(fid)
        counts = Counter(ids)
        duplicates = {fid: n for fid, n in counts.items() if n > 1}
        if not duplicates:
            return []
        return [
            AuditFinding(
                check_name=self.name,
                category=self.category,
                severity="critical",
                message=(
                    f"{len(duplicates)} duplicate finding ID(s) detected: "
                    f"{sorted(duplicates)}; downstream dashboards that "
                    "dedupe on id would silently drop the collisions"
                ),
                affected_keys=[f"findings[*].id={fid}" for fid in sorted(duplicates)],
                evidence={
                    "duplicate_ids": dict(sorted(duplicates.items())),
                    "total_findings": len(ids),
                },
            ),
        ]


class FindingIDNamespaceCheck(AuditCheck):
    """Asserts ``findings[*].id`` use the C02 namespaced format.

    Legacy ``[A-Z]+-NNNN`` IDs are still accepted (so old reports
    parse) but flagged ``warn`` with a migration hint.  IDs that match
    neither pattern are also flagged ``warn`` because they may collide
    cross-project.  Acts as a regression detector for any future PR
    that bypasses :func:`nines.core.identity.format_finding_id`.
    """

    name = "finding_id_namespace"
    category = "finding_id"

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        findings = report.get("findings") or []
        legacy: list[str] = []
        unknown: list[str] = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            fid = f.get("id")
            if not isinstance(fid, str):
                continue
            if _NAMESPACED_ID_RE.match(fid):
                continue
            if _LEGACY_ID_RE.match(fid):
                legacy.append(fid)
            else:
                unknown.append(fid)

        out: list[AuditFinding] = []
        if legacy:
            out.append(
                AuditFinding(
                    check_name=self.name,
                    category=self.category,
                    severity="warn",
                    message=(
                        "legacy ID format detected — may collide cross-project "
                        f"({len(legacy)} legacy ID(s); first few: {legacy[:3]})"
                    ),
                    affected_keys=[f"findings[*].id={fid}" for fid in legacy[:10]],
                    evidence={
                        "legacy_ids": legacy,
                        "expected_pattern": _NAMESPACED_ID_RE.pattern,
                    },
                ),
            )
        if unknown:
            out.append(
                AuditFinding(
                    check_name=self.name,
                    category=self.category,
                    severity="warn",
                    message=(
                        f"unknown finding-ID format ({len(unknown)} ID(s); "
                        f"first few: {unknown[:3]}); expected namespaced "
                        f"{_NAMESPACED_ID_RE.pattern!r}"
                    ),
                    affected_keys=[f"findings[*].id={fid}" for fid in unknown[:10]],
                    evidence={"unknown_ids": unknown},
                ),
            )
        return out


class EconomicsFormulaVersionCheck(AuditCheck):
    """Asserts ``economics.formula_version >= 2`` (C09).

    * Missing ``formula_version`` → ``critical`` (means the economics
      block is from a pre-C09 release without the migration metadata
      that downstream consumers need to interpret the numbers).
    * ``formula_version == 1`` (or any int < 2) → ``warn`` with
      migration hint.
    * ``formula_version >= 2`` → no finding.

    The economics block is expected at
    ``metrics.agent_impact.economics`` per
    :class:`~nines.analyzer.agent_impact.AgentImpactReport`.
    """

    name = "economics_formula_version"
    category = "economics"

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        econ = (report.get("metrics") or {}).get("agent_impact", {}).get("economics", {})
        if not isinstance(econ, dict) or not econ:
            # No economics block — out of scope for this check (e.g.
            # the analyzer was run with --no-agent-impact).
            return []
        if "formula_version" not in econ:
            return [
                AuditFinding(
                    check_name=self.name,
                    category=self.category,
                    severity="critical",
                    message=(
                        "economics.formula_version is missing — pre-C09 "
                        "report or missing migration; downstream consumers "
                        "cannot detect the derivation method"
                    ),
                    affected_keys=[
                        "metrics.agent_impact.economics.formula_version",
                    ],
                    evidence={"economics_keys": sorted(econ)},
                ),
            ]
        version = econ["formula_version"]
        if isinstance(version, int) and version < 2:
            return [
                AuditFinding(
                    check_name=self.name,
                    category=self.category,
                    severity="warn",
                    message=(
                        f"economics.formula_version={version} (< 2); legacy "
                        "v1 derivation detected — re-run analyze to migrate "
                        "to the C09 derived formula"
                    ),
                    affected_keys=[
                        "metrics.agent_impact.economics.formula_version",
                    ],
                    evidence={
                        "formula_version": version,
                        "expected_min": 2,
                    },
                ),
            ]
        return []


class EconomicsBreakEvenSanityCheck(AuditCheck):
    """Detects the §4.6 ``break_even_interactions = 2`` regression.

    In v1 the constant ``2`` was published independently of the actual
    overhead / savings inputs.  After C09, ``break_even`` is
    ``ceil(overhead / max(saved, 1))``.  Therefore a published
    ``break_even == 2`` is only valid when the algebra holds:
    ``saved < overhead <= 2 * saved`` (the boundary that makes
    ``ceil(overhead / saved) == 2``).  Anything else means a future
    PR re-pinned the constant.  Severity ``critical`` because it
    directly recreates the published-bug pattern.
    """

    name = "economics_break_even_sanity"
    category = "economics"

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        econ = (report.get("metrics") or {}).get("agent_impact", {}).get("economics", {})
        if not isinstance(econ, dict) or not econ:
            return []
        be = econ.get("break_even_interactions")
        overhead = econ.get("overhead_tokens", 0)
        saved = econ.get("per_interaction_savings_tokens", 0)
        if not isinstance(be, int) or be != 2:
            return []
        # ceil(overhead / saved) == 2  ⇔  saved < overhead <= 2 * saved
        if (
            isinstance(overhead, int)
            and isinstance(saved, int)
            and saved > 0
            and saved < overhead <= 2 * saved
        ):
            return []
        expected_be: int | None = None
        if isinstance(overhead, int) and isinstance(saved, int) and saved > 0:
            expected_be = (overhead + saved - 1) // saved
        return [
            AuditFinding(
                check_name=self.name,
                category=self.category,
                severity="critical",
                message=(
                    "economics.break_even_interactions == 2 is not "
                    f"algebraically derivable from overhead={overhead} and "
                    f"saved={saved} (expected saved < overhead <= 2*saved); "
                    "looks like the §4.6 constant-2 bug regressing"
                ),
                affected_keys=[
                    "metrics.agent_impact.economics.break_even_interactions",
                    "metrics.agent_impact.economics.overhead_tokens",
                    "metrics.agent_impact.economics.per_interaction_savings_tokens",
                ],
                evidence={
                    "break_even_interactions": be,
                    "overhead_tokens": overhead,
                    "per_interaction_savings_tokens": saved,
                    "expected_break_even": expected_be,
                },
            ),
        ]


class GraphVerificationPassedCheck(AuditCheck):
    """Asserts ``knowledge_graph.verification.passed == True`` (C03).

    Only fires when the report contains a ``knowledge_graph`` block
    (i.e. the graph strategy was used).  After C03 the verifier
    reports ``True`` on the §2 fixtures; this check makes sure a
    future regression that bypasses the verifier signal gets caught.
    Severity ``critical`` so ``--strict-audit`` blocks bad emissions
    in the same way ``--strict-graph`` does today.
    """

    name = "graph_verification_passed"
    category = "knowledge_graph"

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        kg = (report.get("metrics") or {}).get("knowledge_graph")
        if not isinstance(kg, dict) or not kg:
            return []
        ver = kg.get("verification")
        if not isinstance(ver, dict):
            return []
        passed = bool(ver.get("passed", False))
        issues = ver.get("issues") or []
        critical = [i for i in issues if isinstance(i, dict) and i.get("severity") == "critical"]
        if passed and not critical:
            return []
        return [
            AuditFinding(
                check_name=self.name,
                category=self.category,
                severity="critical",
                message=(
                    f"knowledge_graph.verification.passed={passed} with "
                    f"{len(critical)} critical issue(s); strict-audit gate "
                    "would block emission"
                ),
                affected_keys=[
                    "metrics.knowledge_graph.verification.passed",
                    "metrics.knowledge_graph.verification.issues[*]",
                ],
                evidence={
                    "passed": passed,
                    "critical_issue_count": len(critical),
                    "first_critical_issues": critical[:3],
                },
            ),
        ]


class ReportMetadataPresenceCheck(AuditCheck):
    """Asserts the ``report_metadata`` block is present and well-formed.

    The CLI's ``analyze --format json`` always emits this block via
    :meth:`AnalysisPipeline.build_report_metadata`.  A missing field
    indicates a future code path emitted JSON without going through
    the canonical helper — a Wave-1 regression.  Severity ``warn``
    because legacy reports without metadata are still readable, just
    not schema-versioned.
    """

    name = "report_metadata_presence"
    category = "schema_metadata"

    REQUIRED_KEYS: tuple[str, ...] = (
        "id_namespace_version",
        "nines_version",
        "analyzer_schema_version",
    )

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        metadata = report.get("report_metadata")
        if not isinstance(metadata, dict):
            return [
                AuditFinding(
                    check_name=self.name,
                    category=self.category,
                    severity="warn",
                    message=(
                        "top-level report_metadata block is absent; "
                        "downstream parsers cannot detect id namespace "
                        "or schema version"
                    ),
                    affected_keys=["report_metadata"],
                    evidence={"report_top_level_keys": sorted(report)},
                ),
            ]
        missing = [k for k in self.REQUIRED_KEYS if k not in metadata]
        if not missing:
            return []
        return [
            AuditFinding(
                check_name=self.name,
                category=self.category,
                severity="warn",
                message=(
                    "report_metadata is missing required key(s): "
                    f"{sorted(missing)}; expected: "
                    f"{sorted(self.REQUIRED_KEYS)}"
                ),
                affected_keys=[f"report_metadata.{k}" for k in missing],
                evidence={
                    "missing_keys": missing,
                    "present_keys": sorted(metadata),
                },
            ),
        ]


class SchemaVersioningCheck(AuditCheck):
    """Warns when ``analyzer_schema_version`` doesn't match the expectation.

    Migration hook for future schema bumps (e.g.
    ``analyzer_schema_version`` going from ``1`` → ``2``).  Only
    installed when an ``expected_schema_version`` arg is provided to
    :class:`ConsistencyAuditor` — so it is *not* a default built-in.
    Severity ``warn`` because a schema mismatch shouldn't block CI;
    it should prompt the consumer to update its parser.
    """

    name = "schema_versioning"
    category = "schema_metadata"

    def __init__(self, expected_schema_version: int) -> None:
        if not isinstance(expected_schema_version, int):
            raise TypeError(
                "expected_schema_version must be int; got "
                f"{type(expected_schema_version).__name__}",
            )
        self.expected_schema_version = expected_schema_version

    def check(self, report: dict[str, Any]) -> list[AuditFinding]:
        metadata = report.get("report_metadata") or {}
        actual = metadata.get("analyzer_schema_version")
        if actual == self.expected_schema_version:
            return []
        return [
            AuditFinding(
                check_name=self.name,
                category=self.category,
                severity="warn",
                message=(
                    f"analyzer_schema_version mismatch: expected "
                    f"{self.expected_schema_version}, got {actual!r}; "
                    "downstream parsers may need migration"
                ),
                affected_keys=["report_metadata.analyzer_schema_version"],
                evidence={
                    "expected": self.expected_schema_version,
                    "actual": actual,
                },
            ),
        ]


# ---------------------------------------------------------------------------
# Auditor orchestrator
# ---------------------------------------------------------------------------


class ConsistencyAuditor:
    """Runs all configured :class:`AuditCheck` instances on an analyzer report.

    Default behaviour mirrors the C10 revised POC plan — install the
    six built-in checks.  Pass ``checks=`` to override entirely
    (useful for tests that exercise a single check).  Pass
    ``expected_schema_version=N`` to additionally install
    :class:`SchemaVersioningCheck` as a migration guard
    (``audit_schema_versioning`` per the validation row).

    Examples
    --------
    >>> auditor = ConsistencyAuditor()
    >>> result = auditor.audit({"findings": []})
    >>> result.summary["critical"]
    0
    >>> ConsistencyAuditor.should_block(result)
    False
    """

    def __init__(
        self,
        checks: list[AuditCheck] | None = None,
        *,
        expected_schema_version: int | None = None,
    ) -> None:
        if checks is None:
            checks = [
                FindingIDUniquenessCheck(),
                FindingIDNamespaceCheck(),
                EconomicsFormulaVersionCheck(),
                EconomicsBreakEvenSanityCheck(),
                GraphVerificationPassedCheck(),
                ReportMetadataPresenceCheck(),
            ]
        self._checks: list[AuditCheck] = list(checks)
        if expected_schema_version is not None:
            self._checks.append(
                SchemaVersioningCheck(expected_schema_version),
            )

    @property
    def checks(self) -> list[AuditCheck]:
        """Return a copy of the installed checks (for introspection)."""
        return list(self._checks)

    def audit(self, report: dict[str, Any]) -> AuditReport:
        """Run every check and return an aggregated :class:`AuditReport`.

        Parameters
        ----------
        report:
            Plain ``dict`` produced by ``nines analyze --format json``
            (typically loaded from disk via :func:`json.loads`).

        Returns
        -------
        AuditReport
            Aggregated result with all findings and a counts summary.
        """
        if not isinstance(report, dict):
            raise TypeError(
                f"report must be a dict; got {type(report).__name__}",
            )
        all_findings: list[AuditFinding] = []
        for c in self._checks:
            try:
                produced = c.check(report)
            except Exception as exc:  # pragma: no cover - defensive
                # No silent failures (workspace rule): surface a
                # runtime audit finding so callers still see data
                # and the original exception is in the evidence dict
                # for forensic debugging.
                all_findings.append(
                    AuditFinding(
                        check_name=c.name,
                        category=c.category,
                        severity="critical",
                        message=(f"check {c.name} raised {type(exc).__name__}: {exc}"),
                        affected_keys=[],
                        evidence={"exception": repr(exc)},
                    ),
                )
                continue
            all_findings.extend(produced)
        summary = self.summary(all_findings)
        return AuditReport(
            checks_run=[c.name for c in self._checks],
            findings=all_findings,
            summary=summary,
        )

    @staticmethod
    def summary(findings: list[AuditFinding]) -> dict[str, Any]:
        """Aggregate ``findings`` into severity / category counts.

        Returns a dict with keys ``critical``, ``warn``, ``info``,
        and ``by_category`` (mapping category name → count).
        """
        out: dict[str, Any] = {
            "critical": 0,
            "warn": 0,
            "info": 0,
            "by_category": {},
        }
        by_cat: dict[str, int] = {}
        for f in findings:
            sev = f.severity
            if sev in ("critical", "warn", "info"):
                out[sev] = int(out[sev]) + 1
            else:
                # No silent failures — surface unknown severities so a
                # caller mis-typing "Critical" still sees the count.
                out[sev] = int(out.get(sev, 0)) + 1
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
        out["by_category"] = by_cat
        return out

    @staticmethod
    def should_block(audit_report: AuditReport) -> bool:
        """True iff at least one ``critical`` finding was produced."""
        return int(audit_report.summary.get("critical", 0)) > 0
