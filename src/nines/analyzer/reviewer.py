"""AST-based code reviewer producing quality and structure metrics.

Uses Python's ``ast`` module to parse files and extract: function count,
class count, cyclomatic complexity, import dependencies, and lines of code.

Covers: FR-301, FR-302.
"""

from __future__ import annotations

import ast
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from nines.core.errors import AnalyzerError
from nines.core.models import Finding

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Metadata extracted from a single function or method definition."""

    name: str
    qualified_name: str
    lineno: int
    end_lineno: int
    args: list[str]
    decorators: list[str]
    docstring: str | None
    is_async: bool
    complexity: int


@dataclass
class ClassInfo:
    """Metadata extracted from a single class definition."""

    name: str
    qualified_name: str
    lineno: int
    end_lineno: int
    bases: list[str]
    methods: list[FunctionInfo]
    docstring: str | None


@dataclass
class ImportInfo:
    """A single import statement."""

    module: str
    names: list[str]
    is_relative: bool
    lineno: int


@dataclass
class FileReview:
    """Complete review result for a single source file."""

    path: str
    total_lines: int
    function_count: int
    class_count: int
    import_count: int
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[ImportInfo]
    avg_complexity: float
    max_complexity: int
    findings: list[Finding]
    ast_tree: ast.Module | None = field(default=None, repr=False)


class _ComplexityVisitor(ast.NodeVisitor):
    """Counts branching nodes to compute cyclomatic complexity."""

    _BRANCH_TYPES = (
        ast.If,
        ast.For,
        ast.While,
        ast.ExceptHandler,
        ast.With,
        ast.Assert,
    )

    def __init__(self) -> None:
        """Initialize complexity visitor."""
        self.complexity = 1

    def _check_boolop(self, node: ast.AST) -> None:
        """Check boolop."""
        if isinstance(node, ast.BoolOp):
            self.complexity += len(node.values) - 1

    def generic_visit(self, node: ast.AST) -> None:
        """Generic visit."""
        if isinstance(node, self._BRANCH_TYPES):
            self.complexity += 1
        self._check_boolop(node)
        super().generic_visit(node)


def _compute_complexity(node: ast.AST) -> int:
    """Compute complexity."""
    visitor = _ComplexityVisitor()
    visitor.visit(node)
    return visitor.complexity


class _FileVisitor(ast.NodeVisitor):
    """Single-pass AST visitor that extracts functions, classes, and imports."""

    def __init__(self, source_path: str) -> None:
        """Initialize file visitor."""
        self._source_path = source_path
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.imports: list[ImportInfo] = []
        self._class_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function def."""
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function def."""
        self._process_function(node, is_async=True)

    def _process_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> None:
        """Process function."""
        qualified = ".".join([*self._class_stack, node.name])
        args = [a.arg for a in node.args.args]
        decorators = [_decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)
        complexity = _compute_complexity(node)
        end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno

        info = FunctionInfo(
            name=node.name,
            qualified_name=qualified,
            lineno=node.lineno,
            end_lineno=end_lineno,
            args=args,
            decorators=decorators,
            docstring=docstring,
            is_async=is_async,
            complexity=complexity,
        )

        if self._class_stack:
            if self.classes:
                self.classes[-1].methods.append(info)
        else:
            self.functions.append(info)

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class def."""
        bases = [_name_from_node(b) for b in node.bases]
        end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno
        qualified = ".".join([*self._class_stack, node.name])

        cls_info = ClassInfo(
            name=node.name,
            qualified_name=qualified,
            lineno=node.lineno,
            end_lineno=end_lineno,
            bases=bases,
            methods=[],
            docstring=ast.get_docstring(node),
        )
        self.classes.append(cls_info)

        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import."""
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module=alias.name,
                    names=[alias.asname or alias.name],
                    is_relative=False,
                    lineno=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit import from."""
        module = node.module or ""
        names = [a.name for a in (node.names or [])]
        self.imports.append(
            ImportInfo(
                module=module,
                names=names,
                is_relative=(node.level or 0) > 0,
                lineno=node.lineno,
            )
        )


def _decorator_name(node: ast.expr) -> str:
    """Decorator name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_from_node(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ast.dump(node)


def _name_from_node(node: ast.expr) -> str:
    """Name from node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_from_node(node.value)}.{node.attr}"
    return ast.dump(node)


def _file_hash(path: str) -> str:
    """Deterministic 6-char hex prefix derived from the file path."""
    return hashlib.sha256(path.encode()).hexdigest()[:6]


class CodeReviewer:
    """Reviews Python source files using AST analysis.

    Extracts function count, class count, cyclomatic complexity,
    import dependencies, and lines of code.  Outputs structured
    :class:`Finding` instances.
    """

    def review_file(self, path: str | Path) -> FileReview:
        """Parse and review a single Python file.

        Parameters
        ----------
        path:
            Filesystem path to a ``.py`` file.

        Returns
        -------
        FileReview
            Structured review containing metrics and findings.
        """
        path = Path(path)
        if not path.is_file():
            raise AnalyzerError(
                f"File not found: {path}",
                details={"path": str(path)},
            )

        source = path.read_text(encoding="utf-8")
        return self.review_source(source, str(path))

    def review_source(self, source: str, path: str = "<string>") -> FileReview:
        """Review source code provided as a string."""
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            raise AnalyzerError(
                f"Syntax error in {path}: {exc}",
                details={"path": path, "lineno": exc.lineno},
                cause=exc,
            ) from exc

        visitor = _FileVisitor(path)
        visitor.visit(tree)

        total_lines = len(source.splitlines())
        all_functions = list(visitor.functions)
        for cls in visitor.classes:
            all_functions.extend(cls.methods)

        complexities = [f.complexity for f in all_functions] if all_functions else [0]
        avg_complexity = sum(complexities) / max(len(complexities), 1)
        max_complexity = max(complexities) if complexities else 0

        findings = self._generate_findings(
            path, visitor, total_lines, avg_complexity, max_complexity
        )

        return FileReview(
            path=path,
            total_lines=total_lines,
            function_count=len(all_functions),
            class_count=len(visitor.classes),
            import_count=len(visitor.imports),
            functions=visitor.functions,
            classes=visitor.classes,
            imports=visitor.imports,
            avg_complexity=round(avg_complexity, 2),
            max_complexity=max_complexity,
            findings=findings,
            ast_tree=tree,
        )

    def _generate_findings(
        self,
        path: str,
        visitor: _FileVisitor,
        total_lines: int,
        avg_complexity: float,
        max_complexity: int,
    ) -> list[Finding]:
        """Generate findings."""
        findings: list[Finding] = []
        idx = 0
        fhash = _file_hash(path)

        all_funcs = list(visitor.functions)
        for cls in visitor.classes:
            all_funcs.extend(cls.methods)

        for func in all_funcs:
            if func.complexity > 10:
                severity = "error" if func.complexity > 20 else "warning"
                findings.append(
                    Finding(
                        id=f"CC-{fhash}-{idx:04d}",
                        severity=severity,
                        category="complexity",
                        message=(
                            f"Function '{func.qualified_name}' has cyclomatic "
                            f"complexity {func.complexity}"
                        ),
                        location=f"{path}:{func.lineno}",
                        suggestion="Consider breaking this function into smaller pieces.",
                    )
                )
                idx += 1

        findings.append(
            Finding(
                id=f"SUM-{fhash}-{idx:04d}",
                severity="info",
                category="summary",
                message=(
                    f"{path}: {total_lines} lines, "
                    f"{len(all_funcs)} functions, "
                    f"{len(visitor.classes)} classes, "
                    f"{len(visitor.imports)} imports, "
                    f"avg complexity {avg_complexity:.1f}"
                ),
                location=path,
            )
        )
        idx += 1

        dep_modules = sorted({imp.module for imp in visitor.imports if imp.module})
        if dep_modules:
            findings.append(
                Finding(
                    id=f"DEP-{fhash}-{idx:04d}",
                    severity="info",
                    category="dependencies",
                    message=f"Imports: {', '.join(dep_modules)}",
                    location=path,
                )
            )

        return findings
