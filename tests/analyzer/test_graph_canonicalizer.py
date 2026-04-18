"""Tests for ``nines.analyzer.graph_canonicalizer`` (C03 — POC)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nines.analyzer.graph_canonicalizer import (  # noqa: E402
    canonicalize_id,
    canonicalize_pair,
    common_project_root,
)


# ---------------------------------------------------------------------------
# canonicalize_id — happy paths
# ---------------------------------------------------------------------------


def test_canonicalize_relative_file_id_passthrough(tmp_path: Path) -> None:
    """Relative ``file:`` IDs pass through (they're already canonical)."""
    (tmp_path / "foo.py").write_text("")
    out = canonicalize_id("file:foo.py", project_root=tmp_path)
    assert out == "file:foo.py"


def test_canonicalize_absolute_file_id_to_relative(tmp_path: Path) -> None:
    """Absolute ``file:`` IDs become relative to project_root."""
    (tmp_path / "foo.py").write_text("")
    abs_id = f"file:{tmp_path}/foo.py"
    out = canonicalize_id(abs_id, project_root=tmp_path)
    assert out == "file:foo.py"


def test_canonicalize_relative_with_dot_segments(tmp_path: Path) -> None:
    """``..`` segments resolve to canonical paths."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b.py").write_text("")
    out = canonicalize_id("file:a/../b.py", project_root=tmp_path)
    assert out == "file:b.py"


def test_canonicalize_function_id_with_member(tmp_path: Path) -> None:
    """``function:`` IDs preserve the ``::member`` suffix."""
    (tmp_path / "foo.py").write_text("")
    abs_id = f"function:{tmp_path}/foo.py::main"
    out = canonicalize_id(abs_id, project_root=tmp_path)
    assert out == "function:foo.py::main"


def test_canonicalize_class_id_with_member(tmp_path: Path) -> None:
    """``class:`` IDs preserve the ``::Class`` qualifier too."""
    (tmp_path / "foo.py").write_text("")
    abs_id = f"class:{tmp_path}/foo.py::Foo"
    out = canonicalize_id(abs_id, project_root=tmp_path)
    assert out == "class:foo.py::Foo"


def test_canonicalize_module_id(tmp_path: Path) -> None:
    """``module:`` IDs are normalised the same way."""
    (tmp_path / "pkg").mkdir()
    abs_id = f"module:{tmp_path}/pkg"
    out = canonicalize_id(abs_id, project_root=tmp_path)
    assert out == "module:pkg"


def test_canonicalize_path_outside_project_kept_absolute(tmp_path: Path) -> None:
    """Paths outside the project root keep an absolute POSIX form."""
    other = tmp_path.parent / "outside_pkg.py"
    other.write_text("")
    abs_id = f"file:{other}"
    out = canonicalize_id(abs_id, project_root=tmp_path)
    assert out.startswith("file:/")
    assert out.endswith("outside_pkg.py")


# ---------------------------------------------------------------------------
# canonicalize_id — passthrough & error paths
# ---------------------------------------------------------------------------


def test_canonicalize_unknown_prefix_passthrough(tmp_path: Path) -> None:
    """IDs with unknown prefix (``concept:``) are returned verbatim."""
    out = canonicalize_id("concept:knowledge_graph", project_root=tmp_path)
    assert out == "concept:knowledge_graph"


def test_canonicalize_no_colon_passthrough(tmp_path: Path) -> None:
    """IDs lacking a ``:`` separator are returned unchanged."""
    out = canonicalize_id("plain-string", project_root=tmp_path)
    assert out == "plain-string"


def test_canonicalize_rejects_empty_id(tmp_path: Path) -> None:
    """Empty IDs raise ValueError, no silent default."""
    with pytest.raises(ValueError):
        canonicalize_id("", project_root=tmp_path)


def test_canonicalize_rejects_empty_root() -> None:
    """Empty project_root raises ValueError, no silent default."""
    with pytest.raises(ValueError):
        canonicalize_id("file:foo.py", project_root="")


def test_canonicalize_idempotent(tmp_path: Path) -> None:
    """Applying canonicalize twice yields the same result."""
    (tmp_path / "deep" / "nested").mkdir(parents=True)
    (tmp_path / "deep" / "nested" / "x.py").write_text("")
    once = canonicalize_id(f"file:{tmp_path}/deep/nested/x.py", project_root=tmp_path)
    twice = canonicalize_id(once, project_root=tmp_path)
    assert once == twice == "file:deep/nested/x.py"


# ---------------------------------------------------------------------------
# canonicalize_pair & common_project_root
# ---------------------------------------------------------------------------


def test_canonicalize_pair_normalises_both_endpoints(tmp_path: Path) -> None:
    """``canonicalize_pair`` normalises both endpoints with same root."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    src, tgt = canonicalize_pair(
        f"file:{tmp_path}/a.py",
        "file:b.py",
        project_root=tmp_path,
    )
    assert src == "file:a.py"
    assert tgt == "file:b.py"


def test_common_project_root_picks_shared_prefix(tmp_path: Path) -> None:
    """Returns the longest common prefix of supplied paths."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    common = common_project_root([
        str(tmp_path / "a" / "x.py"),
        str(tmp_path / "b" / "y.py"),
    ])
    assert Path(common).resolve() == tmp_path.resolve()


def test_common_project_root_empty_input() -> None:
    """Empty input returns ``"."``."""
    assert common_project_root([]) == "."


# ---------------------------------------------------------------------------
# C03 verifier integration — _check_referential_integrity uses canonicalize_id
# ---------------------------------------------------------------------------


def test_verifier_referential_integrity_canonicalises_paths(tmp_path: Path) -> None:
    """Verifier no longer reports a critical issue when a node uses a relative
    path and an edge endpoint uses the absolute form of the same path
    (the §4.1 baseline regression)."""
    from nines.analyzer.graph_models import (  # local import to avoid module-level cycles
        ArchitectureLayer,
        GraphEdge,
        GraphNode,
        KnowledgeGraph,
    )
    from nines.analyzer.graph_verifier import GraphVerifier

    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    nodes = [
        GraphNode(
            id="file:a.py",
            node_type="file",
            name="a.py",
            file_path=str(tmp_path / "a.py"),
        ),
        GraphNode(
            id="file:b.py",
            node_type="file",
            name="b.py",
            file_path=str(tmp_path / "b.py"),
        ),
    ]
    edges = [
        # Edge endpoints use absolute paths; pre-C03 this would mis-match
        # against the relative node IDs and fire a critical issue.
        GraphEdge(
            source=f"file:{tmp_path}/a.py",
            target=f"file:{tmp_path}/b.py",
            edge_type="imports",
        ),
    ]
    graph = KnowledgeGraph(
        project_name="t", nodes=nodes, edges=edges, layers=[ArchitectureLayer(id="L", name="L")],
    )
    result = GraphVerifier().verify(graph)
    critical = [i for i in result.issues if i.severity == "critical"]
    assert critical == [], (
        f"expected zero critical issues after canonicalisation; got {critical}"
    )
    assert result.passed is True


def test_verifier_layer_coverage_zero_when_no_layers(tmp_path: Path) -> None:
    """C03: when ``graph.layers == []`` the published coverage is 0.0,
    not the 100.0 tautology that the prior implementation produced."""
    from nines.analyzer.graph_models import GraphNode, KnowledgeGraph
    from nines.analyzer.graph_verifier import GraphVerifier

    nodes = [
        GraphNode(id="file:a.py", node_type="file", name="a.py"),
        GraphNode(id="file:b.py", node_type="file", name="b.py"),
    ]
    graph = KnowledgeGraph(project_name="t", nodes=nodes, layers=[])
    result = GraphVerifier().verify(graph)
    assert result.layer_coverage_pct == 0.0
