"""Documentation infrastructure integrity tests."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

from nines import __version__


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_mkdocs_yml(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    sanitized = re.sub(r"!!python/name:\S+", "null", raw)
    data = yaml.safe_load(sanitized)
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def mkdocs_data(repo_root: Path) -> dict:
    return _load_mkdocs_yml(repo_root / "mkdocs.yml")


def _iter_nav_md_paths(node: object) -> list[str]:
    paths: list[str] = []
    if isinstance(node, str):
        if node.endswith(".md"):
            paths.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            paths.extend(_iter_nav_md_paths(v))
    elif isinstance(node, list):
        for item in node:
            paths.extend(_iter_nav_md_paths(item))
    return paths


def _zh_path_for_en_md(rel_path: str) -> str:
    p = Path(rel_path)
    return str(p.with_name(f"{p.stem}.zh{p.suffix}"))


def _load_version_hook(repo_root: Path):
    path = repo_root / "docs/hooks/version_hook.py"
    spec = importlib.util.spec_from_file_location("version_hook", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load version hook from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_nav_entries_exist(repo_root: Path, mkdocs_data: dict) -> None:
    nav = mkdocs_data.get("nav")
    assert nav is not None
    docs = repo_root / "docs"
    for rel in _iter_nav_md_paths(nav):
        target = docs / rel
        assert target.is_file(), f"missing nav doc: {rel}"


def test_i18n_pairs_exist(repo_root: Path, mkdocs_data: dict) -> None:
    nav = mkdocs_data.get("nav")
    assert nav is not None
    docs = repo_root / "docs"
    for rel in _iter_nav_md_paths(nav):
        zh_rel = _zh_path_for_en_md(rel)
        zh_target = docs / zh_rel
        assert zh_target.is_file(), f"missing Chinese pair for {rel}: expected {zh_rel}"


def test_deploy_workflow_has_i18n_dependency(repo_root: Path) -> None:
    wf = (repo_root / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
    assert "pip install" in wf
    assert "mkdocs-static-i18n" in wf


def test_version_hook_reads_version(repo_root: Path) -> None:
    mod = _load_version_hook(repo_root)

    class _Env:
        def __init__(self) -> None:
            self.variables: dict[str, str] = {}

    env = _Env()
    mod.define_env(env)
    assert env.variables.get("nines_version") == __version__


def test_development_plan_pages_exist(repo_root: Path) -> None:
    plan_en = repo_root / "docs/development/plan.md"
    plan_zh = repo_root / "docs/development/plan.zh.md"
    assert plan_en.is_file() and plan_en.stat().st_size > 0
    assert plan_zh.is_file() and plan_zh.stat().st_size > 0
