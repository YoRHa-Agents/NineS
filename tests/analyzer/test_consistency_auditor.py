"""Tests for the C10 cross-artifact consistency auditor.

Covers the six built-in checks plus the :class:`ConsistencyAuditor`
aggregator and the ``should_block`` blocking-decision API.  Each
check is exercised against both a clean and a regressed example so
the matrix protects against false negatives *and* false positives.

Empirical anchor: the C10 §C10 row of
``.local/v2.2.0/validate/02_analytical_validation.md`` mandates
that the auditor detect synthetic regressions of §4.5 (duplicate
finding IDs) and §4.6 (constant-2 ``break_even``) — those are the
``*_fails_on_*`` and ``*_critical_on_*`` cases below.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.analyzer.consistency_auditor import (  # noqa: E402
    AuditCheck,
    AuditFinding,
    ConsistencyAuditor,
    EconomicsBreakEvenSanityCheck,
    EconomicsFormulaVersionCheck,
    FindingIDNamespaceCheck,
    FindingIDUniquenessCheck,
    GraphVerificationPassedCheck,
    ReportMetadataPresenceCheck,
)

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _clean_report() -> dict:
    """Return a minimal but fully-clean analyzer-shaped report dict.

    Mirrors the JSON shape produced by ``nines analyze --format json``
    after Wave 1 (C02 namespaced IDs, C09 derived economics, C03 graph
    verification) — every built-in check should produce zero findings.
    """
    return {
        "target": "/tmp/clean",
        "findings": [
            {"id": "AI-deadbeef-0001", "severity": "info", "category": "x", "message": "m1"},
            {"id": "AI-deadbeef-0002", "severity": "info", "category": "x", "message": "m2"},
        ],
        "metrics": {
            "agent_impact": {
                "economics": {
                    "formula_version": 2,
                    "break_even_interactions": 6,
                    "overhead_tokens": 41343,
                    "per_interaction_savings_tokens": 6919,
                },
            },
            "knowledge_graph": {
                "verification": {
                    "passed": True,
                    "issues": [],
                },
            },
        },
        "report_metadata": {
            "id_namespace_version": 2,
            "nines_version": "3.2.0-test",
            "analyzer_schema_version": 1,
        },
    }


# ---------------------------------------------------------------------------
# FindingIDUniquenessCheck
# ---------------------------------------------------------------------------


def test_finding_id_uniqueness_check_passes_on_unique() -> None:
    """A clean report with all-unique IDs produces zero findings."""
    out = FindingIDUniquenessCheck().check(_clean_report())
    assert out == [], f"unique IDs must produce zero findings; got {[f.message for f in out]}"


def test_finding_id_uniqueness_check_fails_on_duplicates() -> None:
    """Duplicate finding IDs produce exactly one critical finding."""
    report = _clean_report()
    # Force a collision: two findings with the same id.
    report["findings"][1]["id"] = report["findings"][0]["id"]
    out = FindingIDUniquenessCheck().check(report)
    assert len(out) == 1, f"expected 1 finding; got {len(out)}: {out}"
    assert out[0].severity == "critical"
    assert out[0].category == "finding_id"
    assert "AI-deadbeef-0001" in out[0].evidence["duplicate_ids"]
    assert out[0].evidence["duplicate_ids"]["AI-deadbeef-0001"] == 2
    assert out[0].evidence["total_findings"] == 2


# ---------------------------------------------------------------------------
# FindingIDNamespaceCheck
# ---------------------------------------------------------------------------


def test_finding_id_namespace_check_passes_on_namespaced() -> None:
    """C02 namespaced IDs yield zero findings."""
    out = FindingIDNamespaceCheck().check(_clean_report())
    assert out == [], f"namespaced IDs must pass; got {out}"


def test_finding_id_namespace_check_warns_on_legacy_format() -> None:
    """Bare ``[A-Z]+-NNNN`` IDs are flagged with severity ``warn``."""
    report = _clean_report()
    report["findings"] = [
        {"id": "AI-0001", "severity": "info", "category": "x", "message": "legacy 1"},
        {"id": "AI-0002", "severity": "info", "category": "x", "message": "legacy 2"},
    ]
    out = FindingIDNamespaceCheck().check(report)
    assert len(out) == 1, f"expected one warn finding for legacy IDs; got {len(out)}: {out}"
    assert out[0].severity == "warn"
    assert "legacy ID format detected" in out[0].message
    assert out[0].evidence["legacy_ids"] == ["AI-0001", "AI-0002"]


# ---------------------------------------------------------------------------
# EconomicsFormulaVersionCheck
# ---------------------------------------------------------------------------


def test_economics_formula_version_check_passes_on_v2() -> None:
    """Reports already on the C09 formula (version >= 2) produce zero findings."""
    out = EconomicsFormulaVersionCheck().check(_clean_report())
    assert out == [], f"v2 economics must pass; got {out}"


def test_economics_formula_version_check_critical_on_missing() -> None:
    """A pre-C09 economics block (no formula_version) is critical."""
    report = _clean_report()
    del report["metrics"]["agent_impact"]["economics"]["formula_version"]
    out = EconomicsFormulaVersionCheck().check(report)
    assert len(out) == 1
    assert out[0].severity == "critical"
    assert "formula_version is missing" in out[0].message
    assert "metrics.agent_impact.economics.formula_version" in out[0].affected_keys


def test_economics_formula_version_check_warn_on_v1() -> None:
    """Legacy v1 economics is flagged ``warn`` with a migration hint."""
    report = _clean_report()
    report["metrics"]["agent_impact"]["economics"]["formula_version"] = 1
    out = EconomicsFormulaVersionCheck().check(report)
    assert len(out) == 1
    assert out[0].severity == "warn"
    assert "formula_version=1" in out[0].message
    assert out[0].evidence["expected_min"] == 2


# ---------------------------------------------------------------------------
# EconomicsBreakEvenSanityCheck
# ---------------------------------------------------------------------------


def test_economics_break_even_sanity_check_passes_when_derivable() -> None:
    """``break_even == 2`` is fine when ``saved < overhead <= 2*saved``.

    Example: overhead=200, saved=100 → ``ceil(200/100) == 2``.  Also
    asserts the alternative where ``break_even != 2`` always passes.
    """
    report = _clean_report()
    econ = report["metrics"]["agent_impact"]["economics"]
    # Case 1: break_even != 2 (clean baseline, be=6) → no findings.
    out = EconomicsBreakEvenSanityCheck().check(report)
    assert out == [], f"break_even != 2 must pass; got {out}"

    # Case 2: break_even == 2 with overhead == saved * 2 → derivable.
    econ["break_even_interactions"] = 2
    econ["overhead_tokens"] = 200
    econ["per_interaction_savings_tokens"] = 100
    out2 = EconomicsBreakEvenSanityCheck().check(report)
    assert out2 == [], f"break_even == 2 with overhead==2*saved must pass; got {out2}"


def test_economics_break_even_sanity_check_fails_on_regression() -> None:
    """The §4.6 bug pattern (be=2 with mismatched overhead/savings) is critical.

    Mirrors the synthetic regression injected in the empirical-proof
    step: overhead=100000, saved=5000 → real break_even=20, so a
    published be=2 is unjustified.
    """
    report = _clean_report()
    econ = report["metrics"]["agent_impact"]["economics"]
    econ["break_even_interactions"] = 2
    econ["overhead_tokens"] = 100000
    econ["per_interaction_savings_tokens"] = 5000
    out = EconomicsBreakEvenSanityCheck().check(report)
    assert len(out) == 1
    assert out[0].severity == "critical"
    assert "constant-2 bug regressing" in out[0].message
    assert out[0].evidence["break_even_interactions"] == 2
    assert out[0].evidence["overhead_tokens"] == 100000
    assert out[0].evidence["per_interaction_savings_tokens"] == 5000
    # ceil(100000 / 5000) == 20
    assert out[0].evidence["expected_break_even"] == 20


# ---------------------------------------------------------------------------
# GraphVerificationPassedCheck
# ---------------------------------------------------------------------------


def test_graph_verification_passed_check_passes_clean_report() -> None:
    """A clean verification block (passed=True, no critical issues)."""
    out = GraphVerificationPassedCheck().check(_clean_report())
    assert out == [], f"clean verification must pass; got {out}"


def test_graph_verification_passed_check_critical_on_failed() -> None:
    """``verification.passed=False`` with a critical issue is flagged."""
    report = _clean_report()
    report["metrics"]["knowledge_graph"]["verification"] = {
        "passed": False,
        "issues": [
            {
                "severity": "critical",
                "category": "referential_integrity",
                "message": "synthetic critical for test",
            },
        ],
    }
    out = GraphVerificationPassedCheck().check(report)
    assert len(out) == 1
    assert out[0].severity == "critical"
    assert out[0].evidence["passed"] is False
    assert out[0].evidence["critical_issue_count"] == 1


# ---------------------------------------------------------------------------
# ReportMetadataPresenceCheck
# ---------------------------------------------------------------------------


def test_report_metadata_presence_check_passes_when_present() -> None:
    """All three required keys present → zero findings."""
    out = ReportMetadataPresenceCheck().check(_clean_report())
    assert out == [], f"metadata present must pass; got {out}"


def test_report_metadata_presence_check_warns_when_missing() -> None:
    """A missing required key produces one ``warn`` finding."""
    report = _clean_report()
    del report["report_metadata"]["nines_version"]
    out = ReportMetadataPresenceCheck().check(report)
    assert len(out) == 1
    assert out[0].severity == "warn"
    assert "nines_version" in out[0].evidence["missing_keys"]
    assert "report_metadata.nines_version" in out[0].affected_keys

    # Also: a fully absent block is flagged.
    report.pop("report_metadata")
    out2 = ReportMetadataPresenceCheck().check(report)
    assert len(out2) == 1
    assert out2[0].severity == "warn"
    assert out2[0].affected_keys == ["report_metadata"]


# ---------------------------------------------------------------------------
# ConsistencyAuditor — aggregator + should_block
# ---------------------------------------------------------------------------


def test_consistency_auditor_aggregates_findings_correctly() -> None:
    """Auditor combines all check outputs and computes per-severity counts.

    Build a report that triggers two critical findings (duplicate IDs +
    break_even regression) plus one warn (legacy ID format on the
    duplicate finding because we use bare IDs); verify the aggregated
    summary reflects all of them and the by_category breakdown is
    populated correctly.
    """
    report = _clean_report()
    # Duplicate ID → critical (uniqueness)
    report["findings"][1]["id"] = report["findings"][0]["id"]
    # Break-even regression → critical (sanity)
    econ = report["metrics"]["agent_impact"]["economics"]
    econ["break_even_interactions"] = 2
    econ["overhead_tokens"] = 100000
    econ["per_interaction_savings_tokens"] = 5000
    # Drop a metadata key → warn (presence)
    del report["report_metadata"]["nines_version"]

    auditor = ConsistencyAuditor()
    audit = auditor.audit(report)

    assert audit.checks_run == [
        "finding_id_uniqueness",
        "finding_id_namespace",
        "economics_formula_version",
        "economics_break_even_sanity",
        "graph_verification_passed",
        "report_metadata_presence",
    ]
    assert audit.summary["critical"] == 2, (
        f"expected 2 critical findings; summary={audit.summary} "
        f"findings={[(f.check_name, f.severity) for f in audit.findings]}"
    )
    assert audit.summary["warn"] >= 1
    assert audit.summary["info"] == 0
    by_cat = audit.summary["by_category"]
    assert by_cat["finding_id"] >= 1
    assert by_cat["economics"] >= 1
    assert by_cat["schema_metadata"] >= 1
    # Total findings count matches sum of per-severity counts
    total = audit.summary["critical"] + audit.summary["warn"] + audit.summary["info"]
    assert total == len(audit.findings)
    # Round-trip via to_dict
    payload = audit.to_dict()
    assert payload["summary"]["critical"] == 2
    assert payload["checks_run"][0] == "finding_id_uniqueness"


def test_consistency_auditor_should_block_only_on_critical() -> None:
    """``should_block`` returns ``True`` iff any critical finding is present."""
    auditor = ConsistencyAuditor()

    # Clean report → no findings → should_block False
    clean = auditor.audit(_clean_report())
    assert clean.summary["critical"] == 0
    assert ConsistencyAuditor.should_block(clean) is False

    # Warn-only report (legacy IDs) → should_block False
    warn_only = _clean_report()
    warn_only["findings"] = [
        {"id": "AI-0001", "severity": "info", "category": "x", "message": "m"},
    ]
    warn_audit = auditor.audit(warn_only)
    assert warn_audit.summary["warn"] >= 1
    assert warn_audit.summary["critical"] == 0
    assert ConsistencyAuditor.should_block(warn_audit) is False

    # Critical report (duplicate IDs) → should_block True
    crit = _clean_report()
    crit["findings"][1]["id"] = crit["findings"][0]["id"]
    crit_audit = auditor.audit(crit)
    assert crit_audit.summary["critical"] >= 1
    assert ConsistencyAuditor.should_block(crit_audit) is True


# ---------------------------------------------------------------------------
# Bonus regression coverage: schema_versioning hook + dataclass shape
# ---------------------------------------------------------------------------


def test_schema_versioning_check_warns_on_mismatch() -> None:
    """The optional ``audit_schema_versioning`` hook flags version drift."""
    report = _clean_report()
    auditor = ConsistencyAuditor(expected_schema_version=2)
    audit = auditor.audit(report)
    schema_findings = [f for f in audit.findings if f.check_name == "schema_versioning"]
    assert len(schema_findings) == 1
    assert schema_findings[0].severity == "warn"
    assert schema_findings[0].evidence["expected"] == 2
    assert schema_findings[0].evidence["actual"] == 1


def test_audit_finding_is_serialisable_and_subclass_contract() -> None:
    """:class:`AuditFinding` round-trips and :class:`AuditCheck` is abstract."""
    finding = AuditFinding(
        check_name="t",
        category="cat",
        severity="info",
        message="hi",
        affected_keys=["k"],
        evidence={"a": 1},
    )
    assert finding.to_dict() == {
        "check_name": "t",
        "category": "cat",
        "severity": "info",
        "message": "hi",
        "affected_keys": ["k"],
        "evidence": {"a": 1},
    }
    # AuditCheck is abstract — can't instantiate without subclass.
    try:
        AuditCheck()  # type: ignore[abstract]
    except TypeError:
        pass
    else:
        raise AssertionError("AuditCheck must be abstract")
