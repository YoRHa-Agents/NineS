"""Cross-language import graph builder.

Builds a project-internal import dependency graph by parsing source files
in Python, JavaScript/TypeScript, Go, and Rust. Uses deterministic,
AST/regex-based extraction with no LLM dependency.

Covers: FR-318.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nines.analyzer.scanner import FileInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JS / TS import patterns
# ---------------------------------------------------------------------------
_JS_IMPORT_FROM_RE = re.compile(
    r"""(?:import\s+(?:[\w{},*\s]+)\s+from|import)\s+['"]([^'"]+)['"]""",
)
_JS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_DYNAMIC_IMPORT_RE = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")

# ---------------------------------------------------------------------------
# Go import patterns
# ---------------------------------------------------------------------------
_GO_SINGLE_IMPORT_RE = re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE)
_GO_BLOCK_IMPORT_RE = re.compile(
    r"import\s*\((.*?)\)", re.DOTALL,
)
_GO_BLOCK_ITEM_RE = re.compile(r'"([^"]+)"')

# ---------------------------------------------------------------------------
# Rust import patterns
# ---------------------------------------------------------------------------
_RUST_USE_RE = re.compile(
    r"^\s*(?:pub\s+)?use\s+(crate|super|self)(::[\w:{}*,\s]+)\s*;",
    re.MULTILINE,
)
_RUST_MOD_RE = re.compile(r"^\s*(?:pub\s+)?mod\s+(\w+)\s*;", re.MULTILINE)

# ---------------------------------------------------------------------------
# JS / TS resolution suffixes
# ---------------------------------------------------------------------------
_JS_RESOLVE_SUFFIXES = (
    ".ts", ".tsx", ".js", ".jsx",
    "/index.ts", "/index.tsx", "/index.js", "/index.jsx",
)

_LANG_EXTENSIONS: dict[str, set[str]] = {
    "python": {".py"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx", ".mts", ".cts"},
    "go": {".go"},
    "rust": {".rs"},
}


@dataclass
class ImportEdge:
    """A single resolved import relationship between two project files."""

    source_file: str
    target_file: str
    import_name: str
    is_relative: bool
    line_number: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "source_file": self.source_file,
            "target_file": self.target_file,
            "import_name": self.import_name,
            "is_relative": self.is_relative,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportEdge:
        """Deserialize from a plain dictionary."""
        return cls(
            source_file=data["source_file"],
            target_file=data["target_file"],
            import_name=data["import_name"],
            is_relative=data.get("is_relative", False),
            line_number=data.get("line_number", 0),
        )


@dataclass
class ImportGraph:
    """Project-internal import dependency graph."""

    edges: list[ImportEdge] = field(default_factory=list)
    unresolved: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "edges": [e.to_dict() for e in self.edges],
            "unresolved": [
                {"source_file": src, "import_name": name}
                for src, name in self.unresolved
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportGraph:
        """Deserialize from a plain dictionary."""
        edges = [ImportEdge.from_dict(e) for e in data.get("edges", [])]
        unresolved = [
            (item["source_file"], item["import_name"])
            for item in data.get("unresolved", [])
        ]
        return cls(edges=edges, unresolved=unresolved)

    def files_importing(self, target: str) -> list[str]:
        """Return source files that import *target*."""
        return sorted({e.source_file for e in self.edges if e.target_file == target})

    def files_imported_by(self, source: str) -> list[str]:
        """Return files imported by *source*."""
        return sorted({e.target_file for e in self.edges if e.source_file == source})

    def fan_in(self, target: str) -> int:
        """Number of distinct files that import *target*."""
        return len({e.source_file for e in self.edges if e.target_file == target})

    def fan_out(self, source: str) -> int:
        """Number of distinct files imported by *source*."""
        return len({e.target_file for e in self.edges if e.source_file == source})


class ImportGraphBuilder:
    """Builds a cross-language import graph for a project.

    Parses source files using AST (Python) or regex (JS/TS, Go, Rust)
    and resolves import targets to project-internal file paths.
    """

    def __init__(self) -> None:
        self._extractors: dict[str, Any] = {
            "python": self._extract_python_imports,
            "javascript": self._extract_js_ts_imports,
            "typescript": self._extract_js_ts_imports,
            "go": self._extract_go_imports,
            "rust": self._extract_rust_imports,
        }

    def build(
        self,
        project_root: Path,
        files: list[FileInfo],
    ) -> ImportGraph:
        """Build an import graph from scanned *files* under *project_root*.

        Steps:
        1. Build a file index mapping importable names to relative paths.
        2. For each code file extract imports via language-specific parsers.
        3. Resolve imports to project-internal files.
        4. Return the assembled :class:`ImportGraph`.
        """
        file_index = self._build_file_index(project_root, files)
        edges: list[ImportEdge] = []
        unresolved: list[tuple[str, str]] = []

        for fi in files:
            lang: str = getattr(fi, "language", "")
            extractor = self._extractors.get(lang)
            if extractor is None:
                continue

            rel_path = str(Path(fi.path).relative_to(project_root))
            abs_path = Path(fi.path)

            try:
                raw_imports = extractor(abs_path)
            except Exception:
                logger.warning(
                    "Failed to extract imports from %s", rel_path,
                )
                continue

            for import_name, is_relative, lineno in raw_imports:
                resolved = self._resolve_import(
                    rel_path, import_name, is_relative, file_index,
                )
                if resolved is not None:
                    edges.append(ImportEdge(
                        source_file=rel_path,
                        target_file=resolved,
                        import_name=import_name,
                        is_relative=is_relative,
                        line_number=lineno,
                    ))
                else:
                    unresolved.append((rel_path, import_name))

        return ImportGraph(edges=edges, unresolved=unresolved)

    # ------------------------------------------------------------------
    # Language-specific import extractors
    # ------------------------------------------------------------------

    def _extract_python_imports(
        self, path: Path,
    ) -> list[tuple[str, bool, int]]:
        """Extract imports from a Python file using the ``ast`` module.

        Returns a list of ``(import_name, is_relative, lineno)`` tuples.
        """
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            logger.warning("Syntax error parsing %s", path)
            return []

        results: list[tuple[str, bool, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((alias.name, False, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_relative = (node.level or 0) > 0
                if is_relative and module:
                    prefix = "." * (node.level or 0)
                    results.append((prefix + module, True, node.lineno))
                elif is_relative:
                    for alias in node.names:
                        prefix = "." * (node.level or 0)
                        results.append((prefix + alias.name, True, node.lineno))
                else:
                    results.append((module, False, node.lineno))
        return results

    def _extract_js_ts_imports(
        self, path: Path,
    ) -> list[tuple[str, bool, int]]:
        """Extract imports from a JS/TS file using regex patterns.

        Returns a list of ``(import_name, is_relative, lineno)`` tuples.
        """
        source = path.read_text(encoding="utf-8")
        results: list[tuple[str, bool, int]] = []

        for lineno, line in enumerate(source.splitlines(), start=1):
            for match in _JS_IMPORT_FROM_RE.finditer(line):
                name = match.group(1)
                results.append((name, name.startswith("."), lineno))
            for match in _JS_REQUIRE_RE.finditer(line):
                name = match.group(1)
                results.append((name, name.startswith("."), lineno))
            for match in _JS_DYNAMIC_IMPORT_RE.finditer(line):
                name = match.group(1)
                results.append((name, name.startswith("."), lineno))

        return results

    def _extract_go_imports(
        self, path: Path,
    ) -> list[tuple[str, bool, int]]:
        """Extract imports from a Go file using regex patterns.

        Returns a list of ``(import_name, is_relative, lineno)`` tuples.
        Go imports are always absolute package paths; ``is_relative``
        is always ``False``.
        """
        source = path.read_text(encoding="utf-8")
        results: list[tuple[str, bool, int]] = []

        for lineno, line in enumerate(source.splitlines(), start=1):
            m = _GO_SINGLE_IMPORT_RE.match(line)
            if m:
                results.append((m.group(1), False, lineno))

        for block_match in _GO_BLOCK_IMPORT_RE.finditer(source):
            block = block_match.group(1)
            block_start = source[: block_match.start()].count("\n") + 1
            for i, block_line in enumerate(block.splitlines()):
                item = _GO_BLOCK_ITEM_RE.search(block_line)
                if item:
                    results.append((
                        item.group(1), False, block_start + i + 1,
                    ))

        return results

    def _extract_rust_imports(
        self, path: Path,
    ) -> list[tuple[str, bool, int]]:
        """Extract imports from a Rust file using regex patterns.

        Returns a list of ``(import_name, is_relative, lineno)`` tuples.
        Only ``crate::``, ``super::``, and ``self::`` uses are captured,
        since those are project-internal. ``mod`` declarations are also
        captured.
        """
        source = path.read_text(encoding="utf-8")
        results: list[tuple[str, bool, int]] = []

        for lineno, line in enumerate(source.splitlines(), start=1):
            for m in _RUST_USE_RE.finditer(line):
                prefix = m.group(1)
                rest = m.group(2).strip().lstrip(":")
                full = f"{prefix}::{rest}".rstrip(";").strip()
                is_relative = prefix in ("super", "self")
                results.append((full, is_relative, lineno))
            for m in _RUST_MOD_RE.finditer(line):
                results.append((m.group(1), False, lineno))

        return results

    # ------------------------------------------------------------------
    # Import resolution
    # ------------------------------------------------------------------

    def _resolve_import(
        self,
        source_file: str,
        import_name: str,
        is_relative: bool,
        file_index: dict[str, str],
    ) -> str | None:
        """Resolve *import_name* to a project-internal relative file path.

        Returns ``None`` when the import cannot be resolved to a known
        project file (e.g. third-party or stdlib).
        """
        if is_relative and import_name.startswith("."):
            return self._resolve_relative_import(
                source_file, import_name, file_index,
            )

        if import_name in file_index:
            return file_index[import_name]

        parts = import_name.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in file_index:
                return file_index[candidate]

        return None

    def _resolve_relative_import(
        self,
        source_file: str,
        import_name: str,
        file_index: dict[str, str],
    ) -> str | None:
        """Resolve a relative import (Python dot-prefix or JS/TS ./ ../)."""
        source_dir = str(Path(source_file).parent)

        if import_name.startswith("./") or import_name.startswith("../"):
            # JS/TS style relative import — normalise without hitting the
            # real filesystem so paths stay project-relative.
            combined = Path(source_dir) / import_name
            norm = "/".join(
                p for p in combined.parts if p != "."
            )
            # Collapse ".." segments manually
            parts = norm.split("/")
            resolved_parts: list[str] = []
            for p in parts:
                if p == ".." and resolved_parts:
                    resolved_parts.pop()
                else:
                    resolved_parts.append(p)
            norm = "/".join(resolved_parts)

            for suffix in _JS_RESOLVE_SUFFIXES:
                candidate = norm + suffix
                if candidate in file_index:
                    return file_index[candidate]
            if norm in file_index:
                return file_index[norm]
            return None

        # Python dot-prefix relative import
        dots = 0
        rest = import_name
        while rest.startswith("."):
            dots += 1
            rest = rest[1:]

        parts = source_dir.replace("\\", "/").split("/")
        up = dots - 1
        if up > 0:
            parts = parts[:-up] if up < len(parts) else []
        base = ".".join(parts)
        candidate_mod = (f"{base}.{rest}" if base else rest) if rest else base

        if candidate_mod in file_index:
            return file_index[candidate_mod]

        return None

    # ------------------------------------------------------------------
    # File index construction
    # ------------------------------------------------------------------

    def _build_file_index(
        self,
        project_root: Path,
        files: list[FileInfo],
    ) -> dict[str, str]:
        """Map importable names to relative file paths.

        For Python: dotted module names (``pkg.mod``) → relative paths.
        For JS/TS: relative POSIX paths (with and without extension).
        For Go: directory-based package paths.
        For Rust: ``crate::`` prefixed module paths.
        """
        index: dict[str, str] = {}

        for fi in files:
            abs_path = Path(fi.path)
            try:
                rel = abs_path.relative_to(project_root)
            except ValueError:
                continue
            rel_str = rel.as_posix()
            lang: str = getattr(fi, "language", "")

            if lang == "python":
                self._index_python_file(rel, rel_str, index)
            elif lang in ("javascript", "typescript"):
                self._index_js_ts_file(rel, rel_str, index)
            elif lang == "go":
                self._index_go_file(rel, rel_str, index)
            elif lang == "rust":
                self._index_rust_file(rel, rel_str, index)

        return index

    @staticmethod
    def _index_python_file(
        rel: Path, rel_str: str, index: dict[str, str],
    ) -> None:
        """Add Python module entries to the index."""
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            mod_parts = parts[:-1]
        else:
            mod_parts = parts[:]
            mod_parts[-1] = mod_parts[-1].removesuffix(".py")
        if mod_parts:
            index[".".join(mod_parts)] = rel_str

    @staticmethod
    def _index_js_ts_file(
        rel: Path, rel_str: str, index: dict[str, str],
    ) -> None:
        """Add JS/TS file entries to the index."""
        index[rel_str] = rel_str

        no_ext = str(rel.with_suffix(""))
        index[no_ext] = rel_str

        if rel.stem == "index":
            dir_path = str(rel.parent)
            if dir_path != ".":
                index[dir_path] = rel_str

    @staticmethod
    def _index_go_file(
        rel: Path, rel_str: str, index: dict[str, str],
    ) -> None:
        """Add Go package entries to the index."""
        pkg_dir = str(rel.parent)
        if pkg_dir != ".":
            index[pkg_dir] = rel_str

    @staticmethod
    def _index_rust_file(
        rel: Path, rel_str: str, index: dict[str, str],
    ) -> None:
        """Add Rust module entries to the index."""
        parts = list(rel.parts)
        if parts[-1] in ("mod.rs", "lib.rs", "main.rs"):
            mod_parts = parts[:-1]
        else:
            mod_parts = parts[:]
            mod_parts[-1] = mod_parts[-1].removesuffix(".rs")

        if mod_parts:
            crate_path = "crate::" + "::".join(mod_parts)
            index[crate_path] = rel_str
            mod_name = mod_parts[-1]
            index[mod_name] = rel_str
