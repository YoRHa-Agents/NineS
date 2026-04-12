"""Tests for knowledge indexer, search engine, and abstraction layer."""

from __future__ import annotations

import pytest

from nines.analyzer.abstraction import AbstractionLayer, Pattern
from nines.analyzer.indexer import KnowledgeIndex
from nines.analyzer.search import SearchEngine, SearchResult
from nines.core.models import KnowledgeUnit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_units() -> list[KnowledgeUnit]:
    return [
        KnowledgeUnit(
            id="u1",
            source="src/auth/login.py",
            content="def validate_credentials(username, password): checks user credentials against the database",
            unit_type="function",
            metadata={"complexity": 3},
        ),
        KnowledgeUnit(
            id="u2",
            source="src/auth/tokens.py",
            content="def create_jwt_token(user_id, expiry): generates JSON web token for authentication",
            unit_type="function",
            metadata={"complexity": 2},
        ),
        KnowledgeUnit(
            id="u3",
            source="src/data/models.py",
            content="class UserModel: database model for user entities with ORM mapping",
            unit_type="class",
            metadata={"complexity": 5},
        ),
        KnowledgeUnit(
            id="u4",
            source="src/data/repository.py",
            content="class UserRepository: data access layer for user CRUD operations on the database",
            unit_type="class",
            metadata={"complexity": 4},
        ),
        KnowledgeUnit(
            id="u5",
            source="src/api/handlers.py",
            content="def handle_login_request(request): HTTP handler that validates input and returns token",
            unit_type="function",
            relationships={"calls": ["u1", "u2"]},
        ),
    ]


# ---------------------------------------------------------------------------
# KnowledgeIndex
# ---------------------------------------------------------------------------

class TestKnowledgeIndex:
    def test_add_and_get_unit(self) -> None:
        index = KnowledgeIndex()
        unit = KnowledgeUnit(id="u1", content="test content")
        index.add_unit(unit)
        assert index.get_unit("u1") is not None
        assert index.size == 1

    def test_remove_unit(self) -> None:
        index = KnowledgeIndex()
        index.add_unit(KnowledgeUnit(id="u1", content="test"))
        assert index.remove_unit("u1") is True
        assert index.get_unit("u1") is None
        assert index.size == 0

    def test_remove_unit_missing(self) -> None:
        index = KnowledgeIndex()
        assert index.remove_unit("nope") is False

    def test_list_units(self) -> None:
        index = KnowledgeIndex()
        for u in _make_units():
            index.add_unit(u)
        assert len(index.list_units()) == 5

    def test_build_index(self) -> None:
        index = KnowledgeIndex()
        for u in _make_units():
            index.add_unit(u)
        index.build_index()
        assert index._built is True

    def test_query_returns_relevant_results(self) -> None:
        index = KnowledgeIndex()
        for u in _make_units():
            index.add_unit(u)
        index.build_index()

        hits = index.query("database user")
        assert len(hits) > 0
        unit_ids = [uid for uid, _ in hits]
        assert "u3" in unit_ids or "u4" in unit_ids

    def test_query_authentication(self) -> None:
        index = KnowledgeIndex()
        for u in _make_units():
            index.add_unit(u)
        index.build_index()

        hits = index.query("authentication token")
        assert len(hits) > 0
        unit_ids = [uid for uid, _ in hits]
        assert "u2" in unit_ids

    def test_query_empty_returns_nothing(self) -> None:
        index = KnowledgeIndex()
        for u in _make_units():
            index.add_unit(u)
        index.build_index()
        assert index.query("") == []

    def test_query_nonexistent_term(self) -> None:
        index = KnowledgeIndex()
        index.add_unit(KnowledgeUnit(id="u1", content="hello world"))
        index.build_index()
        hits = index.query("zzzznotfound")
        assert hits == []

    def test_auto_build_on_query(self) -> None:
        index = KnowledgeIndex()
        index.add_unit(KnowledgeUnit(id="u1", content="test keyword"))
        hits = index.query("keyword")
        assert len(hits) > 0

    def test_top_k_limit(self) -> None:
        index = KnowledgeIndex()
        for i in range(20):
            index.add_unit(KnowledgeUnit(id=f"u{i}", content=f"common term item {i}"))
        index.build_index()
        hits = index.query("common term", top_k=5)
        assert len(hits) <= 5

    def test_build_empty_index(self) -> None:
        index = KnowledgeIndex()
        index.build_index()
        assert index._built is True
        assert index.query("anything") == []


# ---------------------------------------------------------------------------
# SearchEngine
# ---------------------------------------------------------------------------

class TestSearchEngine:
    def test_search_returns_results(self) -> None:
        engine = SearchEngine()
        for u in _make_units():
            engine.add_unit(u)
        engine.build()

        results = engine.search("database user")
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_result_has_snippet(self) -> None:
        engine = SearchEngine()
        for u in _make_units():
            engine.add_unit(u)
        engine.build()

        results = engine.search("authentication")
        assert len(results) > 0
        assert results[0].snippet != ""

    def test_search_result_to_dict(self) -> None:
        sr = SearchResult(unit_id="u1", score=0.8, snippet="test snippet")
        d = sr.to_dict()
        assert d["unit_id"] == "u1"
        assert d["score"] == 0.8

    def test_search_empty_query(self) -> None:
        engine = SearchEngine()
        engine.add_unit(KnowledgeUnit(id="u1", content="test"))
        engine.build()
        assert engine.search("") == []

    def test_search_relevance_ordering(self) -> None:
        engine = SearchEngine()
        engine.add_unit(KnowledgeUnit(id="u1", content="python programming language"))
        engine.add_unit(KnowledgeUnit(id="u2", content="java enterprise server"))
        engine.add_unit(KnowledgeUnit(id="u3", content="python data science with python libraries"))
        engine.build()

        results = engine.search("python")
        assert len(results) >= 2
        ids = [r.unit_id for r in results]
        assert "u3" in ids
        assert "u1" in ids

    def test_search_top_k(self) -> None:
        engine = SearchEngine()
        for i in range(10):
            engine.add_unit(KnowledgeUnit(id=f"u{i}", content=f"shared keyword {i}"))
        engine.build()
        results = engine.search("shared keyword", top_k=3)
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# AbstractionLayer
# ---------------------------------------------------------------------------

class TestAbstractionLayer:
    def test_extract_naming_patterns(self) -> None:
        units = _make_units()
        layer = AbstractionLayer(min_instances=1, min_confidence=0.1)
        patterns = layer.extract_patterns(units)
        pattern_names = [p.name for p in patterns]
        has_naming = any(p.startswith("naming:") for p in pattern_names)
        assert has_naming

    def test_extract_type_clusters(self) -> None:
        units = _make_units()
        layer = AbstractionLayer(min_instances=2, min_confidence=0.1)
        patterns = layer.extract_patterns(units)
        type_patterns = [p for p in patterns if p.name.startswith("type_cluster:")]
        assert len(type_patterns) > 0
        func_cluster = [p for p in type_patterns if "function" in p.name]
        assert len(func_cluster) == 1
        assert len(func_cluster[0].instances) == 3

    def test_extract_structural_patterns(self) -> None:
        units = [
            KnowledgeUnit(id="a", content="x", relationships={"calls": ["b"]}),
            KnowledgeUnit(id="b", content="y", relationships={"calls": ["c"]}),
        ]
        layer = AbstractionLayer(min_instances=2, min_confidence=0.1)
        patterns = layer.extract_patterns(units)
        structural = [p for p in patterns if p.name.startswith("structural:")]
        assert len(structural) >= 1

    def test_confidence_filtering(self) -> None:
        units = [KnowledgeUnit(id=f"u{i}", content=f"item {i}", unit_type="misc") for i in range(10)]
        units[0] = KnowledgeUnit(id="u0", content="validate_input", unit_type="misc")
        layer = AbstractionLayer(min_instances=1, min_confidence=0.9)
        patterns = layer.extract_patterns(units)
        high_conf = [p for p in patterns if p.name.startswith("naming:")]
        assert all(p.confidence >= 0.9 for p in high_conf)

    def test_pattern_to_dict(self) -> None:
        p = Pattern(name="test", description="desc", instances=["a", "b"], confidence=0.8)
        d = p.to_dict()
        assert d["name"] == "test"
        assert len(d["instances"]) == 2

    def test_empty_units(self) -> None:
        layer = AbstractionLayer()
        patterns = layer.extract_patterns([])
        assert patterns == []

    def test_min_instances_filter(self) -> None:
        units = [
            KnowledgeUnit(id="u1", content="validate_x", unit_type="function"),
        ]
        layer = AbstractionLayer(min_instances=5, min_confidence=0.0)
        patterns = layer.extract_patterns(units)
        naming = [p for p in patterns if p.name.startswith("naming:")]
        assert naming == []
