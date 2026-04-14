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

    class _Conf:
        def __init__(self) -> None:
            self.extra: dict[str, str] = {}

    class _Env:
        def __init__(self) -> None:
            self.variables: dict[str, str] = {}
            self.conf = _Conf()

    env = _Env()
    mod.define_env(env)
    assert env.variables.get("nines_version") == __version__
    assert env.conf.extra.get("nines_version") == __version__


def test_development_plan_pages_exist(repo_root: Path) -> None:
    plan_en = repo_root / "docs/development/plan.md"
    plan_zh = repo_root / "docs/development/plan.zh.md"
    assert plan_en.is_file() and plan_en.stat().st_size > 0
    assert plan_zh.is_file() and plan_zh.stat().st_size > 0


def _get_i18n_languages(mkdocs_data: dict) -> list[dict]:
    for plugin in mkdocs_data.get("plugins", []):
        if isinstance(plugin, dict) and "i18n" in plugin:
            return plugin["i18n"].get("languages", [])
    return []


def test_no_hardcoded_alternate_links(mkdocs_data: dict) -> None:
    """extra.alternate must not be set — the i18n plugin auto-generates it."""
    extra = mkdocs_data.get("extra", {})
    assert "alternate" not in extra, (
        "extra.alternate should be removed; mkdocs-static-i18n with "
        "reconfigure_material auto-generates correct language switcher links"
    )


def test_zh_locale_has_nav_translations(mkdocs_data: dict) -> None:
    languages = _get_i18n_languages(mkdocs_data)
    zh_configs = [lang for lang in languages if lang.get("locale") == "zh"]
    assert zh_configs, "zh locale not found in i18n plugin config"
    zh = zh_configs[0]
    nav_tr = zh.get("nav_translations", {})
    required_keys = ["Home", "User Guide", "Architecture", "Development", "About"]
    for key in required_keys:
        assert key in nav_tr, f"missing nav_translations key: {key}"
        assert nav_tr[key], f"empty translation for: {key}"


def test_zh_locale_has_theme_language(mkdocs_data: dict) -> None:
    languages = _get_i18n_languages(mkdocs_data)
    zh_configs = [lang for lang in languages if lang.get("locale") == "zh"]
    assert zh_configs, "zh locale not found in i18n plugin config"
    zh = zh_configs[0]
    theme = zh.get("theme", {})
    assert theme.get("language") == "zh", (
        "zh locale must set theme.language to 'zh' for Material UI localization"
    )


def test_zh_docs_no_zh_md_links(repo_root: Path) -> None:
    """Chinese docs should link to *.md (not *.zh.md); the i18n plugin resolves locale."""
    docs = repo_root / "docs"
    link_re = re.compile(r"\]\([^)]*\.zh\.md[^)]*\)")
    violations: list[str] = []
    for zh_file in docs.rglob("*.zh.md"):
        content = zh_file.read_text(encoding="utf-8")
        matches = link_re.findall(content)
        if matches:
            rel = zh_file.relative_to(repo_root)
            violations.extend(f"{rel}: {m}" for m in matches)
    assert not violations, (
        f"Found .zh.md internal links (should use .md):\n" + "\n".join(violations)
    )
