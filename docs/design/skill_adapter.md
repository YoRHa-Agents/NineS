# NineS Skill Adapter Design

> **Task**: T17 — Skill Adapter: Multi-Runtime Installation & Template System
> **Input**: `docs/design/skill_interface_spec.md`, `docs/research/gsd_analysis.md`
> **Consumers**: `src/nines/skill/` implementation, `nines install` CLI command
> **Last Modified**: 2026-04-11

---

## Table of Contents

1. [Overview](#1-overview)
2. [JSON Manifest Schema](#2-json-manifest-schema)
3. [Core Interfaces](#3-core-interfaces)
4. [CursorAdapter](#4-cursoradapter)
5. [ClaudeAdapter](#5-claudeadapter)
6. [Template System](#6-template-system)
7. [Installer CLI](#7-installer-cli)
8. [Version Management](#8-version-management)
9. [Runtime Detection](#9-runtime-detection)
10. [Uninstallation](#10-uninstallation)
11. [Configuration](#11-configuration)
12. [Requirement Traceability](#12-requirement-traceability)

---

## 1. Overview

The skill adapter subsystem implements the **single-source multi-target** pattern (GSD Analysis §Pattern 1): NineS commands are defined once in a canonical manifest, then each adapter generates the runtime-specific files needed by Cursor or Claude Code.

### Design Goals

| Goal | Description | Driving Requirements |
|------|-------------|---------------------|
| **Single Source of Truth** | All command metadata lives in one manifest | FR-515, GSD Pattern 1 |
| **Cursor Integration** | Generate `.cursor/skills/nines/` with SKILL.md and command workflows | FR-513 |
| **Claude Code Integration** | Generate `.claude/commands/nines/*.md` + CLAUDE.md section | FR-514 |
| **CLI Installer** | `nines install --target cursor\|claude\|all` | FR-506 |
| **Version Awareness** | Detect existing installs, upgrade/downgrade semantics | FR-516 |
| **Template-Driven** | Jinja2 templates for all generated files | GSD Pattern 1 |
| **Extensible** | New runtimes require only a new adapter class + templates | NFR-16 |

### Architecture Position

```
nines install --target cursor
       │
       ▼
SkillInstaller
       │
       ├──→ ManifestLoader (reads bundled manifest.json)
       ├──→ RuntimeDetector (checks available runtimes)
       ├──→ VersionManager (compares installed vs current)
       ├──→ TemplateEngine (Jinja2 rendering)
       │         │
       │         ├──→ CursorAdapter.emit()
       │         └──→ ClaudeAdapter.emit()
       │
       └──→ writes files to target directory
```

---

## 2. JSON Manifest Schema

The manifest is the single source of truth for the NineS skill. It is authored in JSON (consistent with CON-08: JSON for machine-generated manifests, TOML for user-authored config) and bundled inside the `nines` Python package at `src/nines/skill/manifest.json`.

### 2.1 Complete Schema

```json
{
  "name": "nines",
  "version": "0.1.0",
  "description": "Self-iterating agent toolflow for evaluation, information collection, and knowledge analysis.",
  "author": "YoRHa-Agents",
  "license": "MIT",
  "homepage": "https://github.com/YoRHa-Agents/NineS",
  "manifest_version": 1,

  "dependencies": {
    "python": ">=3.12",
    "package": "nines",
    "cli_binary": "nines"
  },

  "capabilities": {
    "eval": "Run evaluation benchmarks",
    "collect": "Search and track information sources",
    "analyze": "Deep knowledge analysis and decomposition",
    "self-eval": "Self-assessment across capability dimensions",
    "iterate": "Self-improvement iteration cycle",
    "install": "Install/uninstall skill into agent runtimes"
  },

  "commands": {
    "nines-eval": {
      "description": "Run evaluation benchmarks on agent capabilities.",
      "argument_hint": "<task-or-suite> [--scorer TYPE] [--format FORMAT] [--sandbox] [--seed N]",
      "capability": "eval",
      "cli_delegation": "nines eval"
    },
    "nines-collect": {
      "description": "Search and collect information from configured sources.",
      "argument_hint": "<source> <query> [--incremental] [--store PATH] [--limit N]",
      "capability": "collect",
      "cli_delegation": "nines collect"
    },
    "nines-analyze": {
      "description": "Analyze and decompose collected knowledge into structured units.",
      "argument_hint": "<target> [--depth LEVEL] [--decompose] [--index] [--output FORMAT]",
      "capability": "analyze",
      "cli_delegation": "nines analyze"
    },
    "nines-self-eval": {
      "description": "Run self-evaluation across all capability dimensions.",
      "argument_hint": "[--dimensions DIM,...] [--baseline VERSION] [--compare] [--report]",
      "capability": "self-eval",
      "cli_delegation": "nines self-eval"
    },
    "nines-iterate": {
      "description": "Execute a self-improvement iteration cycle.",
      "argument_hint": "[--max-rounds N] [--convergence-threshold F] [--dry-run]",
      "capability": "iterate",
      "cli_delegation": "nines iterate"
    },
    "nines-install": {
      "description": "Install or uninstall NineS as an agent skill.",
      "argument_hint": "--target <cursor|claude|all> [--uninstall] [--global]",
      "capability": "install",
      "cli_delegation": "nines install"
    }
  },

  "runtimes": {
    "cursor": {
      "min_version": "0.50.0",
      "skill_format": "SKILL.md",
      "install_dir": ".cursor/skills/nines/",
      "tool_mapping": {
        "Shell": "Shell",
        "Read": "Read",
        "Write": "Write",
        "Grep": "Grep",
        "Glob": "Glob",
        "Task": "Task"
      }
    },
    "claude": {
      "min_version": "1.0.0",
      "skill_format": "commands/*.md",
      "install_dir": ".claude/commands/nines/",
      "tool_mapping": {
        "Shell": "Bash",
        "Read": "Read",
        "Write": "Write",
        "Grep": "Grep",
        "Glob": "Glob",
        "Task": "Task"
      }
    }
  },

  "platforms": {
    "os": ["linux", "macos", "windows"],
    "architectures": ["x86_64", "aarch64"]
  }
}
```

### 2.2 Field Definitions

| Path | Field | Type | Required | Description |
|------|-------|------|----------|-------------|
| (root) | `name` | string | yes | Package identifier, matches `^[a-z][a-z0-9_-]*$` |
| (root) | `version` | string | yes | SemVer version string |
| (root) | `description` | string | yes | One-line description for skill listings |
| (root) | `manifest_version` | int | yes | Schema version, must be `1` |
| `dependencies` | `python` | string | yes | PEP 440 version specifier |
| `dependencies` | `package` | string | yes | PyPI package name |
| `dependencies` | `cli_binary` | string | yes | CLI binary name on `$PATH` |
| `capabilities` | `<name>` | string | yes | Capability ID → human description |
| `commands.<name>` | `description` | string | yes | Command description |
| `commands.<name>` | `argument_hint` | string | yes | Usage hint string |
| `commands.<name>` | `capability` | string | yes | Must reference a key in `capabilities` |
| `commands.<name>` | `cli_delegation` | string | yes | CLI subcommand this maps to |
| `runtimes.<name>` | `install_dir` | string | yes | Relative install path |
| `runtimes.<name>` | `tool_mapping` | object | yes | Canonical tool name → runtime tool name |

### 2.3 Validation Rules

```python
import re
from packaging.version import Version
from packaging.specifiers import SpecifierSet

MANIFEST_VALIDATION_RULES = {
    "name_pattern": re.compile(r"^[a-z][a-z0-9_-]*$"),
    "manifest_version": 1,
}


def validate_manifest(manifest: SkillManifest) -> list[str]:
    """Validate manifest against all schema rules. Returns list of error messages."""
    errors: list[str] = []

    if not MANIFEST_VALIDATION_RULES["name_pattern"].match(manifest.name):
        errors.append(f"name '{manifest.name}' must match ^[a-z][a-z0-9_-]*$")

    try:
        Version(manifest.version)
    except Exception:
        errors.append(f"version '{manifest.version}' is not valid SemVer")

    try:
        SpecifierSet(manifest.dependencies.python)
    except Exception:
        errors.append(
            f"python specifier '{manifest.dependencies.python}' is not valid PEP 440"
        )

    if manifest.manifest_version != MANIFEST_VALIDATION_RULES["manifest_version"]:
        errors.append(
            f"manifest_version must be {MANIFEST_VALIDATION_RULES['manifest_version']}"
        )

    capability_ids = set(manifest.capabilities.keys())
    for cmd_name, cmd in manifest.commands.items():
        if cmd.capability not in capability_ids:
            errors.append(
                f"command '{cmd_name}' references unknown capability '{cmd.capability}'"
            )

    return errors
```

---

## 3. Core Interfaces

### 3.1 Data Models

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class TargetRuntime(Enum):
    CURSOR = "cursor"
    CLAUDE = "claude"
    ALL = "all"


@dataclass(frozen=True)
class DependencySpec:
    python: str        # PEP 440 specifier
    package: str       # PyPI package name
    cli_binary: str    # CLI binary name


@dataclass(frozen=True)
class CommandDef:
    name: str
    description: str
    argument_hint: str
    capability: str
    cli_delegation: str


@dataclass(frozen=True)
class RuntimeDef:
    name: str
    min_version: str
    skill_format: str
    install_dir: str
    tool_mapping: dict[str, str]


@dataclass(frozen=True)
class SkillManifest:
    """Parsed and validated manifest — the canonical skill definition."""
    name: str
    version: str
    description: str
    author: str
    license: str
    homepage: str
    manifest_version: int
    dependencies: DependencySpec
    capabilities: dict[str, str]
    commands: dict[str, CommandDef]
    runtimes: dict[str, RuntimeDef]

    @classmethod
    def from_json(cls, path: Path) -> SkillManifest:
        """Load and parse a JSON manifest file."""
        ...

    @classmethod
    def bundled(cls) -> SkillManifest:
        """Load the manifest bundled with the nines package."""
        ...

    def to_json(self) -> str:
        """Serialize to JSON for writing into installed directories."""
        ...


@dataclass
class EmittedFile:
    """A single file to be written by an adapter."""
    relative_path: str
    content: str
    description: str


@dataclass
class InstallPlan:
    """Complete plan for what an install operation will do."""
    target: TargetRuntime
    install_dir: Path
    files_to_create: list[EmittedFile]
    files_to_modify: list[tuple[str, str]]  # (path, description)
    existing_version: str | None
    new_version: str
    is_upgrade: bool
    is_downgrade: bool
    is_fresh: bool


@dataclass
class InstallResult:
    """Result of an install or uninstall operation."""
    success: bool
    target: TargetRuntime
    install_dir: Path
    files_created: list[str]
    files_modified: list[str]
    files_removed: list[str]
    version: str
    message: str
```

### 3.2 Protocol Interfaces

```python
@runtime_checkable
class SkillAdapterProtocol(Protocol):
    """Adapter that emits runtime-specific skill files from a manifest."""

    @property
    def runtime_name(self) -> str: ...

    def emit(self, manifest: SkillManifest, template_engine: TemplateEngine) -> list[EmittedFile]:
        """Generate all files needed for this runtime."""
        ...

    def emit_command(
        self, command: CommandDef, manifest: SkillManifest, template_engine: TemplateEngine
    ) -> EmittedFile:
        """Generate a single command file."""
        ...


@runtime_checkable
class TemplateEngineProtocol(Protocol):
    """Renders Jinja2 templates with manifest data."""

    def render(self, template_name: str, context: dict[str, Any]) -> str: ...
    def render_string(self, template_str: str, context: dict[str, Any]) -> str: ...


@runtime_checkable
class VersionManagerProtocol(Protocol):
    """Detects installed version and determines upgrade/downgrade behavior."""

    def get_installed_version(self, install_dir: Path) -> str | None: ...
    def compare_versions(self, installed: str, current: str) -> VersionComparison: ...


@runtime_checkable
class RuntimeDetectorProtocol(Protocol):
    """Auto-detect which agent runtimes are available."""

    def detect(self, project_dir: Path) -> list[TargetRuntime]: ...
    def is_available(self, runtime: TargetRuntime, project_dir: Path) -> bool: ...
```

---

## 4. CursorAdapter

The `CursorAdapter` generates the `.cursor/skills/nines/` directory structure with SKILL.md, command workflows, and reference files.

### 4.1 Generated File Tree

```
.cursor/
└── skills/
    └── nines/
        ├── SKILL.md              # Main skill entry point
        ├── manifest.json         # Installed version manifest
        ├── commands/
        │   ├── eval.md           # nines-eval command workflow
        │   ├── collect.md        # nines-collect command workflow
        │   ├── analyze.md        # nines-analyze command workflow
        │   ├── self-eval.md      # nines-self-eval command workflow
        │   ├── iterate.md        # nines-iterate command workflow
        │   └── install.md        # nines-install command workflow
        └── references/
            ├── capabilities.md   # Capability model reference
            └── config.md         # Configuration reference
```

### 4.2 Class Design

```python
from pathlib import Path


class CursorAdapter:
    """Generates Cursor skill files from the NineS manifest.

    Produces SKILL.md (main entry point), per-command workflow files
    with adapter headers, and reference documents.
    """

    RUNTIME_NAME = "cursor"
    INSTALL_SUBDIR = ".cursor/skills/nines"

    TOOL_MAPPING: dict[str, str] = {
        "Shell": "Shell",
        "Read": "Read",
        "Write": "Write",
        "Grep": "Grep",
        "Glob": "Glob",
        "Task": "Task",
    }

    def __init__(self) -> None:
        self._templates = _CursorTemplates()

    @property
    def runtime_name(self) -> str:
        return self.RUNTIME_NAME

    def emit(
        self,
        manifest: SkillManifest,
        template_engine: TemplateEngine,
    ) -> list[EmittedFile]:
        """Generate all Cursor skill files."""
        files: list[EmittedFile] = []

        files.append(self._emit_skill_md(manifest, template_engine))
        files.append(self._emit_manifest_json(manifest))

        for cmd_name, cmd in manifest.commands.items():
            files.append(self.emit_command(cmd, manifest, template_engine))

        files.append(self._emit_capabilities_ref(manifest, template_engine))
        files.append(self._emit_config_ref(manifest, template_engine))

        return files

    def emit_command(
        self,
        command: CommandDef,
        manifest: SkillManifest,
        template_engine: TemplateEngine,
    ) -> EmittedFile:
        """Generate a single Cursor command workflow file with adapter header."""
        short_name = command.name.removeprefix("nines-")
        context = {
            "command": command,
            "manifest": manifest,
            "tool_mapping": self.TOOL_MAPPING,
            "tools_list": ", ".join(self.TOOL_MAPPING.values()),
        }
        content = template_engine.render(
            f"cursor/command_{short_name}.md.j2",
            context,
        )
        return EmittedFile(
            relative_path=f"commands/{short_name}.md",
            content=content,
            description=f"{command.name} command workflow",
        )

    def _emit_skill_md(
        self, manifest: SkillManifest, template_engine: TemplateEngine
    ) -> EmittedFile:
        context = {
            "manifest": manifest,
            "commands": manifest.commands,
        }
        content = template_engine.render("cursor/SKILL.md.j2", context)
        return EmittedFile(
            relative_path="SKILL.md",
            content=content,
            description="Main skill entry point",
        )

    def _emit_manifest_json(self, manifest: SkillManifest) -> EmittedFile:
        return EmittedFile(
            relative_path="manifest.json",
            content=manifest.to_json(),
            description="Installed version manifest",
        )

    def _emit_capabilities_ref(
        self, manifest: SkillManifest, template_engine: TemplateEngine
    ) -> EmittedFile:
        content = template_engine.render(
            "shared/capabilities.md.j2",
            {"manifest": manifest},
        )
        return EmittedFile(
            relative_path="references/capabilities.md",
            content=content,
            description="Capability model reference",
        )

    def _emit_config_ref(
        self, manifest: SkillManifest, template_engine: TemplateEngine
    ) -> EmittedFile:
        content = template_engine.render(
            "shared/config.md.j2",
            {"manifest": manifest},
        )
        return EmittedFile(
            relative_path="references/config.md",
            content=content,
            description="Configuration reference",
        )
```

### 4.3 SKILL.md Generation

The SKILL.md template follows Cursor's skill protocol: a description block, command table, invocation rules, prerequisites, and examples.

{% raw %}
```jinja2
{# cursor/SKILL.md.j2 #}
# {{ manifest.name | upper }} — {{ manifest.description }}

{{ manifest.name | capitalize }} is an agent skill providing three core capabilities:
**evaluation & benchmarking**, **information collection & tracking**,
and **knowledge analysis & decomposition**. It supports self-assessment
and self-improvement iteration cycles.

## Available Commands

| Command | Description |
|---------|-------------|
{% for cmd_name, cmd in commands.items() %}
| `{{ cmd_name }}` | {{ cmd.description }} |
{% endfor %}

## Invocation

When the user mentions any command above or describes a task matching one of
these capabilities, invoke the corresponding command by reading its workflow
file from `.cursor/skills/{{ manifest.name }}/commands/<command>.md` and
executing it end-to-end.

Treat all user text after the command mention as arguments. If no arguments
are provided, use sensible defaults as described in each command file.

## Prerequisites

{{ manifest.name | capitalize }} must be installed as a Python package.
The `{{ manifest.dependencies.cli_binary }}` CLI binary must be on `$PATH`.
All commands delegate to `{{ manifest.dependencies.cli_binary }} <subcommand>` via the Shell tool.

## Usage Examples

### Run an evaluation suite
User: "nines-eval coding-tasks --scorer composite --format markdown"
→ Read `.cursor/skills/{{ manifest.name }}/commands/eval.md`, execute the workflow.

### Collect GitHub repositories
User: "nines-collect github 'AI agent evaluation' --limit 20"
→ Read `.cursor/skills/{{ manifest.name }}/commands/collect.md`, execute the workflow.

### Run self-evaluation
User: "nines-self-eval --compare --report"
→ Read `.cursor/skills/{{ manifest.name }}/commands/self-eval.md`, execute the workflow.
```
{% endraw %}

### 4.4 Adapter Header Pattern

Each Cursor command file is prefixed with an adapter header that teaches the agent how to invoke the skill (GSD Pattern 2):

{% raw %}
```jinja2
{# cursor/_adapter_header.md.j2 #}
<nines_cursor_adapter>
## A. Skill Invocation
- This command is invoked when the user mentions `{{ command.name }}` or describes
  a task matching the "{{ command.capability }}" capability.
- Treat all user text after the command mention as `{{"{{NINES_ARGS}}"}}`.
- If no arguments are present, treat `{{"{{NINES_ARGS}}"}}` as empty.

## B. Tool Mapping
{% for canonical, native in tool_mapping.items() %}
- Use `{{ native }}` for {{ canonical }} operations.
{% endfor %}

## C. Execution
Run the NineS CLI via Shell and process the results.
</nines_cursor_adapter>
```
{% endraw %}

---

## 5. ClaudeAdapter

The `ClaudeAdapter` generates Claude Code slash commands in `.claude/commands/nines/` and appends a NineS section to `CLAUDE.md`.

### 5.1 Generated File Tree

```
.claude/
├── commands/
│   └── nines/
│       ├── eval.md
│       ├── collect.md
│       ├── analyze.md
│       ├── self-eval.md
│       ├── iterate.md
│       ├── install.md
│       └── manifest.json
└── (CLAUDE.md receives an appended NineS section)
```

### 5.2 Class Design

```python
class ClaudeAdapter:
    """Generates Claude Code command files and CLAUDE.md section.

    Produces per-command files with YAML frontmatter and semantic XML body,
    plus an ambient context section for CLAUDE.md.
    """

    RUNTIME_NAME = "claude"
    INSTALL_SUBDIR = ".claude/commands/nines"
    CLAUDE_MD_START_MARKER = "<!-- nines:start -->"
    CLAUDE_MD_END_MARKER = "<!-- nines:end -->"

    TOOL_MAPPING: dict[str, str] = {
        "Shell": "Bash",
        "Read": "Read",
        "Write": "Write",
        "Grep": "Grep",
        "Glob": "Glob",
        "Task": "Task",
    }

    def __init__(self) -> None:
        self._templates = _ClaudeTemplates()

    @property
    def runtime_name(self) -> str:
        return self.RUNTIME_NAME

    def emit(
        self,
        manifest: SkillManifest,
        template_engine: TemplateEngine,
    ) -> list[EmittedFile]:
        """Generate all Claude Code files."""
        files: list[EmittedFile] = []

        for cmd_name, cmd in manifest.commands.items():
            files.append(self.emit_command(cmd, manifest, template_engine))

        files.append(self._emit_manifest_json(manifest))
        files.append(self._emit_claude_md_section(manifest, template_engine))

        return files

    def emit_command(
        self,
        command: CommandDef,
        manifest: SkillManifest,
        template_engine: TemplateEngine,
    ) -> EmittedFile:
        """Generate a Claude Code slash command file with YAML frontmatter."""
        short_name = command.name.removeprefix("nines-")
        context = {
            "command": command,
            "manifest": manifest,
            "tool_mapping": self.TOOL_MAPPING,
            "allowed_tools": list(self.TOOL_MAPPING.values()),
        }
        content = template_engine.render(
            f"claude/command_{short_name}.md.j2",
            context,
        )
        return EmittedFile(
            relative_path=f"{short_name}.md",
            content=content,
            description=f"nines:{short_name} slash command",
        )

    def _emit_manifest_json(self, manifest: SkillManifest) -> EmittedFile:
        return EmittedFile(
            relative_path="manifest.json",
            content=manifest.to_json(),
            description="Installed version manifest",
        )

    def _emit_claude_md_section(
        self,
        manifest: SkillManifest,
        template_engine: TemplateEngine,
    ) -> EmittedFile:
        """Generate the CLAUDE.md section content (not a file path in install_dir)."""
        context = {"manifest": manifest, "commands": manifest.commands}
        content = template_engine.render("claude/claude_md_section.md.j2", context)
        return EmittedFile(
            relative_path="__CLAUDE_MD_SECTION__",
            content=content,
            description="Content to append to CLAUDE.md",
        )

    def apply_claude_md(
        self,
        project_dir: Path,
        section_content: str,
    ) -> tuple[Path, str]:
        """Append or update the NineS section in CLAUDE.md.

        Returns (path, action) where action is 'created' or 'updated'.
        """
        claude_md = project_dir / "CLAUDE.md"
        marked_content = (
            f"\n{self.CLAUDE_MD_START_MARKER}\n"
            f"{section_content}\n"
            f"{self.CLAUDE_MD_END_MARKER}\n"
        )

        if claude_md.exists():
            existing = claude_md.read_text(encoding="utf-8")
            if self.CLAUDE_MD_START_MARKER in existing:
                import re
                pattern = re.compile(
                    rf"{re.escape(self.CLAUDE_MD_START_MARKER)}.*?"
                    rf"{re.escape(self.CLAUDE_MD_END_MARKER)}",
                    re.DOTALL,
                )
                updated = pattern.sub(marked_content.strip(), existing)
                claude_md.write_text(updated, encoding="utf-8")
                return claude_md, "updated"
            else:
                claude_md.write_text(
                    existing.rstrip() + "\n" + marked_content,
                    encoding="utf-8",
                )
                return claude_md, "updated"
        else:
            claude_md.write_text(marked_content.lstrip(), encoding="utf-8")
            return claude_md, "created"

    def remove_claude_md_section(self, project_dir: Path) -> bool:
        """Remove the NineS section from CLAUDE.md. Returns True if modified."""
        claude_md = project_dir / "CLAUDE.md"
        if not claude_md.exists():
            return False

        content = claude_md.read_text(encoding="utf-8")
        if self.CLAUDE_MD_START_MARKER not in content:
            return False

        import re
        pattern = re.compile(
            rf"\n?{re.escape(self.CLAUDE_MD_START_MARKER)}.*?"
            rf"{re.escape(self.CLAUDE_MD_END_MARKER)}\n?",
            re.DOTALL,
        )
        cleaned = pattern.sub("", content).strip()

        if not cleaned:
            claude_md.unlink()
        else:
            claude_md.write_text(cleaned + "\n", encoding="utf-8")
        return True
```

### 5.3 Claude Command File Format

Each command file uses YAML frontmatter + semantic XML body (matching Claude Code's native format):

{% raw %}
```jinja2
{# claude/command_eval.md.j2 #}
---
name: nines:eval
description: {{ command.description }}
argument-hint: "{{ command.argument_hint }}"
allowed-tools:
{% for tool in allowed_tools %}
  - {{ tool }}
{% endfor %}
---

<objective>
Execute NineS evaluation benchmarks. Parse user arguments, run the eval pipeline
via the `nines` CLI, and present structured results.
</objective>

<process>
1. Parse $ARGUMENTS to extract: task/suite identifier, scorer type, output format, flags.
2. Validate that the `nines` CLI is installed: `which nines`.
3. Run the evaluation:
   ```bash
   nines eval $ARGUMENTS
   ```
4. If `--output` flag was specified, read the output file and present results.
5. If no `--output`, parse stdout for the results summary.
6. Present results to the user in the requested format (default: markdown table).
</process>

<error_handling>
- Exit code 1: Invalid arguments → show usage hint from `nines eval --help`.
- Exit code 2: Task/suite not found → list available tasks.
- Exit code 3: Execution failure → show stderr, suggest debug steps.
- Exit code 5: Sandbox error → check sandbox configuration.
- If `nines` not found → advise `pip install nines` or `uv pip install nines`.
</error_handling>
```
{% endraw %}

### 5.4 CLAUDE.md Section Template

{% raw %}
```jinja2
{# claude/claude_md_section.md.j2 #}
## NineS Agent Toolflow

This project uses NineS for evaluation, information collection, and knowledge analysis.

### Available Commands
{% for cmd_name, cmd in commands.items() %}
- `/nines:{{ cmd_name | replace("nines-", "") }}` — {{ cmd.description }}
{% endfor %}

### Configuration
NineS configuration: `nines.toml` (project root) or `~/.config/nines/config.toml` (global).

### Quick Reference
- Run evaluations: `/nines:eval <suite>`
- Collect repos: `/nines:collect github "<query>"`
- Full self-eval: `/nines:self-eval --report`
- Self-improve: `/nines:iterate --max-rounds 3`
```
{% endraw %}

---

## 6. Template System

The template system uses Jinja2 to render all generated files from templates bundled with the `nines` package.

### 6.1 Template Directory Layout

```
src/nines/skill/templates/
├── cursor/
│   ├── SKILL.md.j2
│   ├── _adapter_header.md.j2
│   ├── command_eval.md.j2
│   ├── command_collect.md.j2
│   ├── command_analyze.md.j2
│   ├── command_self-eval.md.j2
│   ├── command_iterate.md.j2
│   └── command_install.md.j2
├── claude/
│   ├── claude_md_section.md.j2
│   ├── command_eval.md.j2
│   ├── command_collect.md.j2
│   ├── command_analyze.md.j2
│   ├── command_self-eval.md.j2
│   ├── command_iterate.md.j2
│   └── command_install.md.j2
└── shared/
    ├── capabilities.md.j2
    └── config.md.j2
```

### 6.2 TemplateEngine Class

```python
from pathlib import Path
from typing import Any

import jinja2


class TemplateEngine:
    """Jinja2-based template engine for rendering skill files.

    Loads templates from the bundled template directory and provides
    rendering with manifest data and adapter-specific context.
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._register_filters()

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a named template with the given context."""
        template = self._env.get_template(template_name)
        return template.render(**context)

    def render_string(self, template_str: str, context: dict[str, Any]) -> str:
        """Render an inline template string."""
        template = self._env.from_string(template_str)
        return template.render(**context)

    def _register_filters(self) -> None:
        self._env.filters["snake_case"] = _to_snake_case
        self._env.filters["kebab_case"] = _to_kebab_case
        self._env.filters["cmd_short_name"] = lambda s: s.removeprefix("nines-")


def _to_snake_case(value: str) -> str:
    return value.replace("-", "_").replace(" ", "_").lower()


def _to_kebab_case(value: str) -> str:
    return value.replace("_", "-").replace(" ", "-").lower()
```

### 6.3 Template Context Variables

All templates receive these standard context variables:

| Variable | Type | Description |
|----------|------|-------------|
| `manifest` | `SkillManifest` | The full parsed manifest |
| `command` | `CommandDef` | The current command (in command templates) |
| `commands` | `dict[str, CommandDef]` | All commands (in index templates) |
| `tool_mapping` | `dict[str, str]` | Canonical → runtime tool mapping |
| `allowed_tools` | `list[str]` | Runtime-native tool names |

---

## 7. Installer CLI

The `nines install` command is the user-facing entry point for skill installation.

### 7.1 SkillInstaller Class

```python
import json
import shutil
from pathlib import Path

from nines.core.errors import NinesError, ConfigError


class SkillInstaller:
    """Orchestrates skill installation across target runtimes.

    Coordinates manifest loading, version checking, template rendering,
    and file writing for each target runtime.
    """

    ADAPTERS: dict[str, SkillAdapterProtocol] = {
        "cursor": CursorAdapter(),
        "claude": ClaudeAdapter(),
    }

    def __init__(
        self,
        manifest: SkillManifest | None = None,
        template_engine: TemplateEngine | None = None,
        version_manager: VersionManagerProtocol | None = None,
        runtime_detector: RuntimeDetectorProtocol | None = None,
    ) -> None:
        self._manifest = manifest or SkillManifest.bundled()
        self._templates = template_engine or TemplateEngine()
        self._versions = version_manager or VersionManager()
        self._detector = runtime_detector or RuntimeDetector()

    def install(
        self,
        target: TargetRuntime,
        project_dir: Path = Path("."),
        global_install: bool = False,
        force: bool = False,
        dry_run: bool = False,
    ) -> InstallResult:
        """Install NineS skill into the target runtime(s)."""
        errors = validate_manifest(self._manifest)
        if errors:
            raise ConfigError(f"Invalid manifest: {'; '.join(errors)}")

        targets = self._resolve_targets(target, project_dir)
        results: list[InstallResult] = []

        for runtime_name in targets:
            adapter = self.ADAPTERS[runtime_name]
            result = self._install_single(
                adapter=adapter,
                project_dir=project_dir,
                global_install=global_install,
                force=force,
                dry_run=dry_run,
            )
            results.append(result)

        if len(results) == 1:
            return results[0]

        return InstallResult(
            success=all(r.success for r in results),
            target=target,
            install_dir=project_dir,
            files_created=[f for r in results for f in r.files_created],
            files_modified=[f for r in results for f in r.files_modified],
            files_removed=[],
            version=self._manifest.version,
            message="\n".join(r.message for r in results),
        )

    def plan(
        self,
        target: TargetRuntime,
        project_dir: Path = Path("."),
        global_install: bool = False,
    ) -> list[InstallPlan]:
        """Generate install plans without executing them (for --dry-run)."""
        targets = self._resolve_targets(target, project_dir)
        plans: list[InstallPlan] = []

        for runtime_name in targets:
            adapter = self.ADAPTERS[runtime_name]
            install_dir = self._resolve_install_dir(
                adapter, project_dir, global_install
            )
            existing_version = self._versions.get_installed_version(install_dir)
            comparison = (
                self._versions.compare_versions(existing_version, self._manifest.version)
                if existing_version
                else None
            )
            files = adapter.emit(self._manifest, self._templates)
            plans.append(InstallPlan(
                target=TargetRuntime(runtime_name),
                install_dir=install_dir,
                files_to_create=[f for f in files if f.relative_path != "__CLAUDE_MD_SECTION__"],
                files_to_modify=(
                    [("CLAUDE.md", "Append NineS section")]
                    if runtime_name == "claude"
                    else []
                ),
                existing_version=existing_version,
                new_version=self._manifest.version,
                is_upgrade=comparison == VersionComparison.UPGRADE if comparison else False,
                is_downgrade=comparison == VersionComparison.DOWNGRADE if comparison else False,
                is_fresh=existing_version is None,
            ))

        return plans

    def _install_single(
        self,
        adapter: SkillAdapterProtocol,
        project_dir: Path,
        global_install: bool,
        force: bool,
        dry_run: bool,
    ) -> InstallResult:
        install_dir = self._resolve_install_dir(adapter, project_dir, global_install)

        version_check = self._check_version(install_dir, force)
        if version_check is not None:
            return version_check

        files = adapter.emit(self._manifest, self._templates)

        if dry_run:
            return self._dry_run_result(adapter, install_dir, files)

        created: list[str] = []
        modified: list[str] = []

        if install_dir.exists():
            shutil.rmtree(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)

        for emitted in files:
            if emitted.relative_path == "__CLAUDE_MD_SECTION__":
                if isinstance(adapter, ClaudeAdapter):
                    path, action = adapter.apply_claude_md(
                        project_dir, emitted.content
                    )
                    modified.append(f"{path} ({action})")
                continue

            file_path = install_dir / emitted.relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(emitted.content, encoding="utf-8")
            created.append(str(file_path.relative_to(project_dir)))

        runtime_label = adapter.runtime_name
        return InstallResult(
            success=True,
            target=TargetRuntime(runtime_label),
            install_dir=install_dir,
            files_created=created,
            files_modified=modified,
            files_removed=[],
            version=self._manifest.version,
            message=(
                f"NineS v{self._manifest.version} installed to {install_dir.relative_to(project_dir)}/\n"
                f"  Created: SKILL.md, {len(created) - 2} commands, "
                f"{sum(1 for f in created if 'references' in f)} references"
            ),
        )

    def _resolve_targets(
        self, target: TargetRuntime, project_dir: Path
    ) -> list[str]:
        if target == TargetRuntime.ALL:
            detected = self._detector.detect(project_dir)
            if not detected:
                raise NinesError(
                    "No supported runtimes detected. "
                    "Use --target cursor or --target claude explicitly."
                )
            return [d.value for d in detected]
        return [target.value]

    def _resolve_install_dir(
        self,
        adapter: SkillAdapterProtocol,
        project_dir: Path,
        global_install: bool,
    ) -> Path:
        runtime_def = self._manifest.runtimes.get(adapter.runtime_name)
        if runtime_def is None:
            raise ConfigError(f"No runtime definition for '{adapter.runtime_name}'")

        if global_install:
            return Path.home() / runtime_def.install_dir
        return project_dir / runtime_def.install_dir

    def _check_version(
        self, install_dir: Path, force: bool
    ) -> InstallResult | None:
        existing = self._versions.get_installed_version(install_dir)
        if existing is None:
            return None

        comparison = self._versions.compare_versions(existing, self._manifest.version)

        if comparison == VersionComparison.SAME and not force:
            return InstallResult(
                success=True,
                target=TargetRuntime.CURSOR,
                install_dir=install_dir,
                files_created=[],
                files_modified=[],
                files_removed=[],
                version=existing,
                message=f"NineS v{existing} already installed. Use --force to reinstall.",
            )

        if comparison == VersionComparison.DOWNGRADE and not force:
            return InstallResult(
                success=False,
                target=TargetRuntime.CURSOR,
                install_dir=install_dir,
                files_created=[],
                files_modified=[],
                files_removed=[],
                version=existing,
                message=(
                    f"Installed v{existing} is newer than package v{self._manifest.version}. "
                    "Use --force to downgrade."
                ),
            )

        return None

    def _dry_run_result(
        self,
        adapter: SkillAdapterProtocol,
        install_dir: Path,
        files: list[EmittedFile],
    ) -> InstallResult:
        lines: list[str] = []
        for f in files:
            if f.relative_path == "__CLAUDE_MD_SECTION__":
                lines.append(f"[dry-run] Would update: CLAUDE.md ({len(f.content)} bytes)")
            else:
                path = install_dir / f.relative_path
                lines.append(
                    f"[dry-run] Would create: {path} ({len(f.content)} bytes)"
                )
        return InstallResult(
            success=True,
            target=TargetRuntime(adapter.runtime_name),
            install_dir=install_dir,
            files_created=[],
            files_modified=[],
            files_removed=[],
            version=self._manifest.version,
            message="\n".join(lines),
        )
```

### 7.2 CLI Entry Point

```python
import click
from pathlib import Path


@click.command("install")
@click.option(
    "--target", "-t",
    type=click.Choice(["cursor", "claude", "all"]),
    required=True,
    help="Target runtime: cursor, claude, or all.",
)
@click.option("--uninstall", is_flag=True, help="Remove NineS skill from target.")
@click.option("--global", "global_install", is_flag=True, help="Install to global user directory.")
@click.option("--project-dir", type=click.Path(exists=True), default=".", help="Project root.")
@click.option("--dry-run", is_flag=True, help="Show what would be done without writing.")
@click.option("--force", is_flag=True, help="Overwrite existing installation.")
def install_command(
    target: str,
    uninstall: bool,
    global_install: bool,
    project_dir: str,
    dry_run: bool,
    force: bool,
) -> None:
    """Install or uninstall NineS as an agent skill."""
    installer = SkillInstaller()
    target_enum = TargetRuntime(target)
    project = Path(project_dir).resolve()

    if uninstall:
        result = installer.uninstall(target_enum, project, global_install)
    elif dry_run:
        plans = installer.plan(target_enum, project, global_install)
        for plan in plans:
            _print_plan(plan)
        return
    else:
        result = installer.install(
            target_enum, project, global_install, force, dry_run=False
        )

    if result.success:
        click.echo(f"✓ {result.message}")
    else:
        click.echo(f"✗ {result.message}", err=True)
        raise SystemExit(1)


def _print_plan(plan: InstallPlan) -> None:
    """Print a dry-run install plan."""
    click.echo(f"\n[{plan.target.value}] Install plan for {plan.install_dir}:")
    if plan.is_fresh:
        click.echo("  Action: Fresh install")
    elif plan.is_upgrade:
        click.echo(f"  Action: Upgrade {plan.existing_version} → {plan.new_version}")
    elif plan.is_downgrade:
        click.echo(f"  Action: Downgrade {plan.existing_version} → {plan.new_version} (requires --force)")

    for f in plan.files_to_create:
        click.echo(f"  [create] {f.relative_path} ({len(f.content)} bytes) — {f.description}")
    for path, desc in plan.files_to_modify:
        click.echo(f"  [modify] {path} — {desc}")
```

---

## 8. Version Management

The `VersionManager` handles installed version detection and comparison semantics (FR-516).

### 8.1 Version Comparison

```python
import enum
import json
from pathlib import Path

from packaging.version import Version


class VersionComparison(enum.Enum):
    SAME = "same"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class VersionManager:
    """Detect installed versions and determine upgrade/downgrade behavior."""

    def get_installed_version(self, install_dir: Path) -> str | None:
        """Read version from the installed manifest.json."""
        manifest_path = install_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return data.get("version")
        except (json.JSONDecodeError, OSError):
            return None

    def compare_versions(
        self, installed: str, current: str
    ) -> VersionComparison:
        """Compare installed version against the package version."""
        try:
            v_installed = Version(installed)
            v_current = Version(current)
        except Exception:
            return VersionComparison.UPGRADE

        if v_installed == v_current:
            return VersionComparison.SAME
        elif v_installed < v_current:
            return VersionComparison.UPGRADE
        else:
            return VersionComparison.DOWNGRADE
```

### 8.2 Version Behavior Matrix

| Installed | Package | `--force` | Behavior |
|-----------|---------|-----------|----------|
| None | v0.1.0 | N/A | Fresh install |
| v0.1.0 | v0.1.0 | No | Skip: "already installed" |
| v0.1.0 | v0.1.0 | Yes | Reinstall (remove + install) |
| v0.1.0 | v0.2.0 | N/A | Upgrade in-place |
| v0.2.0 | v0.1.0 | No | Warn: "installed is newer" |
| v0.2.0 | v0.1.0 | Yes | Downgrade (remove + install) |

---

## 9. Runtime Detection

The `RuntimeDetector` auto-detects available runtimes when `--target all` is used.

```python
import shutil
from pathlib import Path


class RuntimeDetector:
    """Detect which agent runtimes are available in a project or system."""

    DETECTION_RULES: dict[str, list[callable]] = {
        "cursor": [
            lambda p: (p / ".cursor").is_dir(),
            lambda _: shutil.which("cursor") is not None,
        ],
        "claude": [
            lambda p: (p / ".claude").is_dir(),
            lambda _: shutil.which("claude") is not None,
            lambda p: (p / "CLAUDE.md").exists(),
        ],
    }

    def detect(self, project_dir: Path) -> list[TargetRuntime]:
        """Detect all available runtimes."""
        detected: list[TargetRuntime] = []
        for runtime_name, checks in self.DETECTION_RULES.items():
            if any(check(project_dir) for check in checks):
                detected.append(TargetRuntime(runtime_name))
        return detected

    def is_available(
        self, runtime: TargetRuntime, project_dir: Path
    ) -> bool:
        """Check if a specific runtime is available."""
        checks = self.DETECTION_RULES.get(runtime.value, [])
        return any(check(project_dir) for check in checks)
```

### Detection Signals

| Runtime | Detection Signals |
|---------|------------------|
| Cursor | `.cursor/` directory exists OR `cursor` binary on `$PATH` |
| Claude Code | `.claude/` directory exists OR `claude` binary on `$PATH` OR `CLAUDE.md` exists |

---

## 10. Uninstallation

### 10.1 Cursor Uninstall

```python
def uninstall_cursor(self, project_dir: Path, global_install: bool) -> InstallResult:
    install_dir = self._resolve_install_dir(
        self.ADAPTERS["cursor"], project_dir, global_install
    )
    if not install_dir.exists():
        return InstallResult(
            success=False, target=TargetRuntime.CURSOR,
            install_dir=install_dir, files_created=[], files_modified=[],
            files_removed=[], version="",
            message=f"NineS is not installed at {install_dir}",
        )

    shutil.rmtree(install_dir)
    removed = [str(install_dir)]

    skills_dir = install_dir.parent
    if skills_dir.exists() and not any(skills_dir.iterdir()):
        skills_dir.rmdir()

    return InstallResult(
        success=True, target=TargetRuntime.CURSOR,
        install_dir=install_dir, files_created=[], files_modified=[],
        files_removed=removed, version="",
        message=f"NineS removed from {install_dir.relative_to(project_dir)}/",
    )
```

### 10.2 Claude Code Uninstall

```python
def uninstall_claude(self, project_dir: Path, global_install: bool) -> InstallResult:
    adapter = self.ADAPTERS["claude"]
    install_dir = self._resolve_install_dir(adapter, project_dir, global_install)
    removed: list[str] = []
    modified: list[str] = []

    if install_dir.exists():
        shutil.rmtree(install_dir)
        removed.append(str(install_dir))

    commands_dir = install_dir.parent
    if commands_dir.exists() and not any(commands_dir.iterdir()):
        commands_dir.rmdir()

    if isinstance(adapter, ClaudeAdapter):
        if adapter.remove_claude_md_section(project_dir):
            modified.append("CLAUDE.md (NineS section removed)")

    return InstallResult(
        success=True, target=TargetRuntime.CLAUDE,
        install_dir=install_dir, files_created=[], files_modified=modified,
        files_removed=removed, version="",
        message=f"NineS removed from {install_dir.relative_to(project_dir)}/ and CLAUDE.md",
    )
```

### 10.3 Unified Uninstall

```python
def uninstall(
    self,
    target: TargetRuntime,
    project_dir: Path,
    global_install: bool = False,
) -> InstallResult:
    """Remove NineS skill from the target runtime(s)."""
    if target == TargetRuntime.CURSOR:
        return self.uninstall_cursor(project_dir, global_install)
    elif target == TargetRuntime.CLAUDE:
        return self.uninstall_claude(project_dir, global_install)
    elif target == TargetRuntime.ALL:
        r1 = self.uninstall_cursor(project_dir, global_install)
        r2 = self.uninstall_claude(project_dir, global_install)
        return InstallResult(
            success=r1.success or r2.success,
            target=TargetRuntime.ALL,
            install_dir=project_dir,
            files_created=[],
            files_modified=r1.files_modified + r2.files_modified,
            files_removed=r1.files_removed + r2.files_removed,
            version="",
            message=f"{r1.message}\n{r2.message}",
        )
    raise ConfigError(f"Unknown target: {target}")
```

---

## 11. Configuration

Skill adapter settings are part of the `NinesConfig` hierarchy under `[skill]`:

```toml
[skill]
default_target = "all"

[skill.cursor]
install_dir = ".cursor/skills/nines/"

[skill.claude]
install_dir = ".claude/commands/nines/"
update_claude_md = true

[skill.templates]
custom_dir = ""  # empty = use bundled templates
```

### Module Layout in Source Tree

```
src/nines/skill/
├── __init__.py         # Public: SkillInstaller, InstallResult
├── manifest.py         # SkillManifest, ManifestLoader, validation
├── manifest.json       # Bundled manifest (single source of truth)
├── adapters/
│   ├── __init__.py     # AdapterRegistry
│   ├── base.py         # SkillAdapterProtocol, EmittedFile
│   ├── cursor.py       # CursorAdapter
│   └── claude.py       # ClaudeAdapter
├── templates/
│   ├── cursor/         # Cursor Jinja2 templates
│   ├── claude/         # Claude Code Jinja2 templates
│   └── shared/         # Shared reference templates
├── engine.py           # TemplateEngine (Jinja2 wrapper)
├── installer.py        # SkillInstaller orchestrator
├── versions.py         # VersionManager, VersionComparison
├── detector.py         # RuntimeDetector
└── cli.py              # Click command: nines install
```

---

## 12. Requirement Traceability

| Requirement | Section | How Addressed |
|-------------|---------|---------------|
| **FR-506** CLI `nines install` | §7 | `SkillInstaller` + Click command with `--target`, `--uninstall`, `--dry-run`, `--force` |
| **FR-513** Cursor Skill Adapter | §4 | `CursorAdapter` generates SKILL.md, 6 command files, 2 reference files |
| **FR-514** Claude Code Adapter | §5 | `ClaudeAdapter` generates 6 command files + CLAUDE.md section with markers |
| **FR-515** Skill Manifest | §2 | JSON manifest with 5 validation rules (name, SemVer, PEP 440, capability consistency, version) |
| **FR-516** Version Management | §8 | `VersionManager` with same/upgrade/downgrade detection and `--force` semantics |
| **NFR-16** Runtime adapter cost | §3, §4, §5 | New runtime = 1 `SkillAdapterProtocol` subclass + template directory |
| **CON-08** JSON/TOML split | §2 | JSON for both source and installed manifest (machine-generated artifact); TOML reserved for user-authored config |
| **CON-09** Protocol interfaces | §3 | All components defined as Python Protocol classes |
| **CON-10** Cursor + Claude MVP | §4, §5 | Two adapters implemented; architecture supports additional runtimes |
| GSD Pattern 1 | §1, §6 | Single-source multi-target via manifest + per-runtime adapters |
| GSD Pattern 2 | §4.4 | Adapter header injection for Cursor (no native slash-command support) |
| GSD Pattern 3 | §4.2, §5.2 | Per-runtime `TOOL_MAPPING` dictionaries |

---

*Last modified: 2026-04-12*
