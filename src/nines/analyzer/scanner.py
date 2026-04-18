"""Multi-language project scanner.

Discovers, categorizes, and inventories all files in a project
directory.  Detects programming languages, file categories, and
frameworks using deterministic heuristics (no LLM).

Covers: FR-317.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".bat": "batch",
    ".md": "markdown",
    ".rst": "restructuredtext",
    ".adoc": "asciidoc",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".xml": "xml",
    ".svg": "svg",
    ".vue": "vue",
    ".svelte": "svelte",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".tf": "terraform",
    ".txt": "plaintext",
    ".env": "dotenv",
    ".properties": "properties",
    ".csv": "csv",
}

_SPECIAL_FILENAMES: dict[str, str] = {
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    "Jenkinsfile": "groovy",
    "Vagrantfile": "ruby",
    "Gemfile": "ruby",
    "Rakefile": "ruby",
    "CMakeLists.txt": "cmake",
    "docker-compose.yml": "yaml",
    "docker-compose.yaml": "yaml",
}

_CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".mts",
        ".cts",
        ".go",
        ".rs",
        ".java",
        ".rb",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cxx",
        ".cs",
        ".swift",
        ".kt",
        ".kts",
        ".php",
        ".vue",
        ".svelte",
    }
)

_CONFIG_EXTENSIONS = frozenset(
    {
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".env",
        ".properties",
    }
)

_DOCS_EXTENSIONS = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".adoc",
    }
)

_DATA_EXTENSIONS = frozenset(
    {
        ".sql",
        ".graphql",
        ".gql",
        ".proto",
        ".csv",
    }
)

_SCRIPT_EXTENSIONS = frozenset(
    {
        ".sh",
        ".bash",
        ".ps1",
        ".bat",
    }
)

_MARKUP_EXTENSIONS = frozenset(
    {
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".xml",
        ".svg",
    }
)

_INFRA_FILENAMES = frozenset(
    {
        "Dockerfile",
        "Makefile",
        "Jenkinsfile",
        "Vagrantfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }
)

_INFRA_PATH_MARKERS = frozenset(
    {
        ".github",
        ".gitlab-ci.yml",
        ".circleci",
        ".travis.yml",
    }
)

FRAMEWORK_INDICATORS: dict[str, list[str]] = {
    "package.json": [
        "react",
        "vue",
        "angular",
        "@angular/core",
        "next",
        "nuxt",
        "express",
        "fastify",
        "koa",
        "nest",
        "svelte",
        "electron",
        "tailwindcss",
    ],
    "pyproject.toml": [
        "django",
        "flask",
        "fastapi",
        "click",
        "pydantic",
        "celery",
        "sqlalchemy",
        "pytest",
        "httpx",
        "starlette",
    ],
    "setup.py": [
        "django",
        "flask",
        "fastapi",
        "click",
        "pydantic",
    ],
    "Cargo.toml": [
        "tokio",
        "actix",
        "rocket",
        "warp",
        "axum",
        "serde",
        "clap",
        "diesel",
    ],
    "go.mod": [
        "gin",
        "echo",
        "fiber",
        "chi",
        "mux",
        "grpc",
    ],
    "Gemfile": [
        "rails",
        "sinatra",
        "hanami",
        "rspec",
    ],
    "build.gradle": [
        "spring",
        "springboot",
        "ktor",
        "micronaut",
    ],
    "pom.xml": [
        "spring",
        "springboot",
        "quarkus",
        "micronaut",
    ],
}

_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "dist",
        "build",
        ".eggs",
    }
)


@dataclass
class FileInfo:
    """Metadata for a single discovered file."""

    path: str
    language: str
    category: str
    line_count: int = 0
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "path": self.path,
            "language": self.language,
            "category": self.category,
            "line_count": self.line_count,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileInfo:
        """Deserialize from a plain dictionary."""
        return cls(
            path=data["path"],
            language=data.get("language", ""),
            category=data.get("category", ""),
            line_count=data.get("line_count", 0),
            size_bytes=data.get("size_bytes", 0),
        )


@dataclass
class ScanResult:
    """Complete project scan result."""

    project_root: str
    project_name: str
    description: str = ""
    files: list[FileInfo] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    language_breakdown: dict[str, int] = field(default_factory=dict)
    category_breakdown: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "project_root": self.project_root,
            "project_name": self.project_name,
            "description": self.description,
            "files": [f.to_dict() for f in self.files],
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "language_breakdown": dict(self.language_breakdown),
            "category_breakdown": dict(self.category_breakdown),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanResult:
        """Deserialize from a plain dictionary."""
        return cls(
            project_root=data.get("project_root", ""),
            project_name=data.get("project_name", ""),
            description=data.get("description", ""),
            files=[FileInfo.from_dict(f) for f in data.get("files", [])],
            languages=list(data.get("languages", [])),
            frameworks=list(data.get("frameworks", [])),
            total_files=data.get("total_files", 0),
            total_lines=data.get("total_lines", 0),
            language_breakdown=dict(data.get("language_breakdown", {})),
            category_breakdown=dict(data.get("category_breakdown", {})),
            metadata=data.get("metadata", {}),
        )


class ProjectScanner:
    """Discovers and categorizes all files in a project directory."""

    def __init__(self, skip_dirs: frozenset[str] | None = None) -> None:
        self._skip_dirs = skip_dirs or _SKIP_DIRS

    def scan(self, path: str | Path) -> ScanResult:
        """Scan a project directory and return a :class:`ScanResult`.

        Parameters
        ----------
        path:
            Root directory to scan.
        """
        root = Path(path).resolve()
        if not root.is_dir():
            logger.warning("Not a directory: %s", root)
            return ScanResult(
                project_root=str(root),
                project_name=root.name,
            )

        files: list[FileInfo] = []
        for fpath in sorted(root.rglob("*")):
            if not fpath.is_file():
                continue
            if self._should_skip(fpath, root):
                continue

            language = self._detect_language(fpath)
            category = self._classify_category(fpath, language, root)
            line_count = self._count_lines(fpath)
            try:
                size_bytes = fpath.stat().st_size
            except OSError:
                size_bytes = 0

            files.append(
                FileInfo(
                    path=str(fpath),
                    language=language,
                    category=category,
                    line_count=line_count,
                    size_bytes=size_bytes,
                )
            )

        lang_counter: Counter[str] = Counter()
        cat_counter: Counter[str] = Counter()
        total_lines = 0
        for fi in files:
            if fi.language:
                lang_counter[fi.language] += 1
            cat_counter[fi.category] += 1
            total_lines += fi.line_count

        languages = [lang for lang, _ in lang_counter.most_common()]
        frameworks = self._detect_frameworks(root)
        name, description = self._extract_project_info(root)

        return ScanResult(
            project_root=str(root),
            project_name=name,
            description=description,
            files=files,
            languages=languages,
            frameworks=frameworks,
            total_files=len(files),
            total_lines=total_lines,
            language_breakdown=dict(lang_counter),
            category_breakdown=dict(cat_counter),
        )

    def _detect_language(self, path: Path) -> str:
        """Detect programming language from file extension or name."""
        name = path.name
        if name in _SPECIAL_FILENAMES:
            return _SPECIAL_FILENAMES[name]
        return LANGUAGE_MAP.get(path.suffix.lower(), "")

    def _classify_category(
        self,
        path: Path,
        language: str,
        root: Path,
    ) -> str:
        """Classify a file into a category."""
        name = path.name
        suffix = path.suffix.lower()

        if name in _INFRA_FILENAMES:
            return "infra"
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            rel_parts = ()
        if any(p in _INFRA_PATH_MARKERS or p == ".github" for p in rel_parts):
            return "infra"
        if suffix == ".tf":
            return "infra"

        if suffix in _CODE_EXTENSIONS:
            return "code"
        if suffix in _CONFIG_EXTENSIONS:
            return "config"
        if suffix in _DOCS_EXTENSIONS:
            return "docs"
        if suffix in _DATA_EXTENSIONS:
            return "data"
        if suffix in _SCRIPT_EXTENSIONS:
            return "script"
        if suffix in _MARKUP_EXTENSIONS:
            return "markup"

        if language == "dockerfile":
            return "infra"
        if language == "makefile":
            return "infra"

        return "code" if language else "config"

    def _detect_frameworks(self, root: Path) -> list[str]:
        """Detect frameworks by scanning manifest files."""
        detected: list[str] = []
        for manifest_name, indicators in FRAMEWORK_INDICATORS.items():
            manifest_path = root / manifest_name
            if not manifest_path.is_file():
                continue
            try:
                content = manifest_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).lower()
            except OSError as exc:
                logger.debug("Could not read %s: %s", manifest_path, exc)
                continue

            for indicator in indicators:
                if indicator.lower() in content and indicator not in detected:
                    detected.append(indicator)

        return sorted(detected)

    def _extract_project_info(self, root: Path) -> tuple[str, str]:
        """Extract project name and description from manifests."""
        for manifest in ("pyproject.toml", "package.json", "Cargo.toml"):
            mpath = root / manifest
            if not mpath.is_file():
                continue
            try:
                content = mpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if manifest == "package.json":
                return self._parse_package_json(content, root.name)
            if manifest == "pyproject.toml":
                return self._parse_pyproject_toml(content, root.name)
            if manifest == "Cargo.toml":
                return self._parse_cargo_toml(content, root.name)

        return root.name, ""

    @staticmethod
    def _parse_package_json(content: str, fallback: str) -> tuple[str, str]:
        """Extract name and description from package.json."""
        try:
            data = json.loads(content)
            return (
                data.get("name", fallback),
                data.get("description", ""),
            )
        except (json.JSONDecodeError, TypeError):
            return fallback, ""

    @staticmethod
    def _parse_pyproject_toml(content: str, fallback: str) -> tuple[str, str]:
        """Extract name and description from pyproject.toml (regex-based)."""
        import re

        name = fallback
        description = ""
        m = re.search(r'name\s*=\s*"([^"]+)"', content)
        if m:
            name = m.group(1)
        m = re.search(r'description\s*=\s*"([^"]+)"', content)
        if m:
            description = m.group(1)
        return name, description

    @staticmethod
    def _parse_cargo_toml(content: str, fallback: str) -> tuple[str, str]:
        """Extract name and description from Cargo.toml (regex-based)."""
        import re

        name = fallback
        description = ""
        m = re.search(r'name\s*=\s*"([^"]+)"', content)
        if m:
            name = m.group(1)
        m = re.search(r'description\s*=\s*"([^"]+)"', content)
        if m:
            description = m.group(1)
        return name, description

    @staticmethod
    def _count_lines(path: Path) -> int:
        """Count lines in a file, handling encoding errors."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return len(content.splitlines())
        except OSError as exc:
            logger.debug("Could not count lines in %s: %s", path, exc)
            return 0

    def _should_skip(self, path: Path, root: Path) -> bool:
        """Check whether a path should be skipped."""
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            return True
        return any(part in self._skip_dirs or part.startswith(".") for part in rel_parts)
