"""Directory structure analyzer.

Walks directory trees, identifies Python packages and modules, counts files
by type, calculates module coupling via cross-package imports, and generates
a dependency map.

Covers: FR-303, FR-304.
"""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nines.core.errors import AnalyzerError

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".hg", ".svn", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".venv", "venv", ".eggs", "*.egg-info",
})


@dataclass
class FileTypeCounts:
    """Counts of files grouped by extension."""

    counts: dict[str, int] = field(default_factory=dict)
    total: int = 0


@dataclass
class PackageInfo:
    """Information about a discovered Python package."""

    name: str
    path: str
    module_count: int
    has_init: bool


@dataclass
class DependencyMap:
    """Cross-package dependency graph."""

    edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    @property
    def modules(self) -> set[str]:
        result: set[str] = set(self.edges.keys())
        for targets in self.edges.values():
            result |= targets
        return result

    def coupling_for(self, module: str) -> dict[str, int]:
        """Return afferent (Ca) and efferent (Ce) coupling for *module*."""
        efferent = len(self.edges.get(module, set()))
        afferent = sum(
            1 for targets in self.edges.values() if module in targets
        )
        return {"afferent": afferent, "efferent": efferent}


@dataclass
class StructureReport:
    """Output of structure analysis for a directory."""

    root: str
    packages: list[PackageInfo]
    file_type_counts: FileTypeCounts
    python_module_count: int
    dependency_map: DependencyMap
    coupling_metrics: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "packages": [
                {"name": p.name, "path": p.path, "module_count": p.module_count,
                 "has_init": p.has_init}
                for p in self.packages
            ],
            "file_type_counts": {
                "counts": self.file_type_counts.counts,
                "total": self.file_type_counts.total,
            },
            "python_module_count": self.python_module_count,
            "dependency_map": {
                k: sorted(v) for k, v in self.dependency_map.edges.items()
            },
            "coupling_metrics": self.coupling_metrics,
        }


class StructureAnalyzer:
    """Analyzes directory structure for Python projects.

    Walks the directory tree to identify packages and modules, counts
    files by extension, resolves internal import dependencies, and
    computes coupling metrics.
    """

    def analyze_directory(self, path: str | Path) -> StructureReport:
        """Analyze the directory at *path* and return a :class:`StructureReport`."""
        root = Path(path)
        if not root.is_dir():
            raise AnalyzerError(
                f"Not a directory: {root}",
                details={"path": str(root)},
            )

        packages = self._discover_packages(root)
        file_counts = self._count_file_types(root)
        py_files = self._collect_python_files(root)
        module_map = self._build_module_map(root, py_files)
        dep_map = self._resolve_dependencies(root, py_files, module_map)
        coupling = self._compute_coupling(dep_map, module_map)

        return StructureReport(
            root=str(root),
            packages=packages,
            file_type_counts=file_counts,
            python_module_count=len(py_files),
            dependency_map=dep_map,
            coupling_metrics=coupling,
        )

    def _should_skip(self, name: str) -> bool:
        if name.startswith("."):
            return True
        return name in _SKIP_DIRS

    def _discover_packages(self, root: Path) -> list[PackageInfo]:
        packages: list[PackageInfo] = []
        for dirpath in sorted(root.rglob("*")):
            if not dirpath.is_dir():
                continue
            if any(self._should_skip(p) for p in dirpath.relative_to(root).parts):
                continue

            has_init = (dirpath / "__init__.py").is_file()
            py_count = sum(1 for f in dirpath.iterdir() if f.suffix == ".py" and f.is_file())
            if py_count == 0:
                continue

            try:
                rel = dirpath.relative_to(root)
                name = ".".join(rel.parts) if rel.parts else root.name
            except ValueError:
                name = dirpath.name

            packages.append(PackageInfo(
                name=name,
                path=str(dirpath),
                module_count=py_count,
                has_init=has_init,
            ))

        if (root / "__init__.py").is_file() or any(
            f.suffix == ".py" for f in root.iterdir() if f.is_file()
        ):
            py_count = sum(1 for f in root.iterdir() if f.suffix == ".py" and f.is_file())
            if py_count > 0:
                packages.insert(0, PackageInfo(
                    name=root.name,
                    path=str(root),
                    module_count=py_count,
                    has_init=(root / "__init__.py").is_file(),
                ))

        return packages

    def _count_file_types(self, root: Path) -> FileTypeCounts:
        counts: dict[str, int] = defaultdict(int)
        total = 0
        for fpath in root.rglob("*"):
            if not fpath.is_file():
                continue
            if any(self._should_skip(p) for p in fpath.relative_to(root).parts):
                continue
            ext = fpath.suffix or "(no ext)"
            counts[ext] += 1
            total += 1
        return FileTypeCounts(counts=dict(counts), total=total)

    def _collect_python_files(self, root: Path) -> list[Path]:
        result: list[Path] = []
        for fpath in sorted(root.rglob("*.py")):
            if any(self._should_skip(p) for p in fpath.relative_to(root).parts):
                continue
            result.append(fpath)
        return result

    def _build_module_map(self, root: Path, py_files: list[Path]) -> dict[str, Path]:
        """Map dotted module names to file paths."""
        mod_map: dict[str, Path] = {}
        for fpath in py_files:
            rel = fpath.relative_to(root)
            parts = list(rel.parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].removesuffix(".py")
            if parts:
                mod_map[".".join(parts)] = fpath
        return mod_map

    def _resolve_dependencies(
        self,
        root: Path,
        py_files: list[Path],
        module_map: dict[str, Path],
    ) -> DependencyMap:
        dep_map = DependencyMap()
        known_modules = set(module_map.keys())

        for fpath in py_files:
            rel = fpath.relative_to(root)
            parts = list(rel.parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].removesuffix(".py")
            if not parts:
                continue
            source_mod = ".".join(parts)

            try:
                source = fpath.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(fpath))
            except (SyntaxError, UnicodeDecodeError):
                logger.warning("Failed to parse %s for dependency analysis", fpath)
                continue

            for node in ast.walk(tree):
                target = self._resolve_import_node(node, known_modules)
                if target and target != source_mod:
                    dep_map.edges[source_mod].add(target)

        return dep_map

    def _resolve_import_node(
        self, node: ast.AST, known_modules: set[str]
    ) -> str | None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    return alias.name
                prefix = self._find_prefix(alias.name, known_modules)
                if prefix:
                    return prefix
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in known_modules:
                return module
            prefix = self._find_prefix(module, known_modules)
            if prefix:
                return prefix
        return None

    @staticmethod
    def _find_prefix(name: str, known: set[str]) -> str | None:
        parts = name.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in known:
                return candidate
        return None

    def _compute_coupling(
        self,
        dep_map: DependencyMap,
        module_map: dict[str, Path],
    ) -> dict[str, dict[str, Any]]:
        metrics: dict[str, dict[str, Any]] = {}
        for mod in module_map:
            info = dep_map.coupling_for(mod)
            ca, ce = info["afferent"], info["efferent"]
            instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0
            metrics[mod] = {
                "afferent_coupling": ca,
                "efferent_coupling": ce,
                "instability": round(instability, 3),
            }
        return metrics
