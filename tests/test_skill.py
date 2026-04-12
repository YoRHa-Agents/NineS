"""Tests for the NineS skill packaging subsystem."""

from __future__ import annotations

from pathlib import Path

import tomllib

from nines.skill.adapters import ClaudeAdapter, CursorAdapter
from nines.skill.installer import SkillInstaller
from nines.skill.manifest import SkillManifest


class TestManifestGeneration:
    """Test that SkillManifest.generate() produces valid TOML."""

    def test_manifest_generation(self) -> None:
        manifest = SkillManifest()
        toml_str = manifest.generate()

        assert isinstance(toml_str, str)
        assert len(toml_str) > 0

        parsed = tomllib.loads(toml_str)
        assert parsed["manifest"]["name"] == "nines"
        assert parsed["manifest"]["version"] == manifest.version
        assert parsed["manifest"]["manifest_version"] == 1

    def test_manifest_contains_all_capabilities(self) -> None:
        manifest = SkillManifest()
        toml_str = manifest.generate()
        parsed = tomllib.loads(toml_str)

        expected = {"eval", "collect", "analyze", "self-eval", "iterate", "install"}
        assert set(parsed["capabilities"]) == expected

    def test_manifest_contains_commands(self) -> None:
        manifest = SkillManifest()
        toml_str = manifest.generate()
        parsed = tomllib.loads(toml_str)

        assert "nines-eval" in parsed["commands"]
        assert "nines-collect" in parsed["commands"]
        for cmd_data in parsed["commands"].values():
            assert "description" in cmd_data
            assert "argument_hint" in cmd_data
            assert "capability" in cmd_data

    def test_manifest_contains_dependencies(self) -> None:
        manifest = SkillManifest()
        toml_str = manifest.generate()
        parsed = tomllib.loads(toml_str)

        deps = parsed["dependencies"]
        assert deps["python"] == ">=3.12"
        assert deps["package"] == "nines"
        assert deps["cli_binary"] == "nines"

    def test_manifest_roundtrip_is_valid_toml(self) -> None:
        manifest = SkillManifest()
        toml_str = manifest.generate()
        reparsed = tomllib.loads(toml_str)
        assert reparsed["manifest"]["author"] == "YoRHa-Agents"


class TestCursorAdapterGeneratesSkillMd:
    """Test that CursorAdapter emits SKILL.md and command files."""

    def test_cursor_adapter_generates_skill_md(self) -> None:
        adapter = CursorAdapter()
        manifest = SkillManifest()
        files = adapter.emit(manifest)

        paths = [f.relative_path for f in files]
        assert "SKILL.md" in paths

        skill_md = next(f for f in files if f.relative_path == "SKILL.md")
        assert "NINES" in skill_md.content
        assert "Available Commands" in skill_md.content
        assert "nines-eval" in skill_md.content

    def test_cursor_adapter_generates_command_files(self) -> None:
        adapter = CursorAdapter()
        manifest = SkillManifest()
        files = adapter.emit(manifest)

        command_files = [f for f in files if f.relative_path.startswith("commands/")]
        assert len(command_files) == 6

        cmd_names = {f.relative_path for f in command_files}
        assert "commands/eval.md" in cmd_names
        assert "commands/collect.md" in cmd_names
        assert "commands/install.md" in cmd_names

    def test_cursor_adapter_runtime_name(self) -> None:
        adapter = CursorAdapter()
        assert adapter.runtime_name == "cursor"


class TestClaudeAdapterGeneratesCommands:
    """Test that ClaudeAdapter emits command files and CLAUDE.md section."""

    def test_claude_adapter_generates_commands(self) -> None:
        adapter = ClaudeAdapter()
        manifest = SkillManifest()
        files = adapter.emit(manifest)

        real_files = [f for f in files if f.relative_path != "__CLAUDE_MD_SECTION__"]
        assert len(real_files) == 6

        eval_file = next(f for f in real_files if f.relative_path == "eval.md")
        assert "nines:eval" in eval_file.content
        assert "allowed-tools" in eval_file.content

    def test_claude_adapter_generates_claude_md_section(self) -> None:
        adapter = ClaudeAdapter()
        manifest = SkillManifest()
        files = adapter.emit(manifest)

        section = next(f for f in files if f.relative_path == "__CLAUDE_MD_SECTION__")
        assert "<!-- nines:start -->" in section.content
        assert "<!-- nines:end -->" in section.content
        assert "NineS Agent Toolflow" in section.content

    def test_claude_adapter_runtime_name(self) -> None:
        adapter = ClaudeAdapter()
        assert adapter.runtime_name == "claude"


class TestInstallerCreatesFiles:
    """Test that SkillInstaller writes files to disk."""

    def test_installer_creates_files(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("cursor", project_dir=tmp_path)

        assert len(created) > 0

        skill_md = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text(encoding="utf-8")
        assert "NINES" in content

    def test_installer_creates_command_files(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        installer.install("cursor", project_dir=tmp_path)

        commands_dir = tmp_path / ".cursor" / "skills" / "nines" / "commands"
        assert commands_dir.is_dir()
        assert (commands_dir / "eval.md").exists()
        assert (commands_dir / "collect.md").exists()

    def test_installer_claude_target(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("claude", project_dir=tmp_path)

        assert len(created) > 0
        eval_file = tmp_path / ".claude" / "commands" / "nines" / "eval.md"
        assert eval_file.exists()

    def test_installer_all_target(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("all", project_dir=tmp_path)

        cursor_skill = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        claude_eval = tmp_path / ".claude" / "commands" / "nines" / "eval.md"
        assert cursor_skill.exists()
        assert claude_eval.exists()

    def test_uninstall_removes_directory(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        installer.install("cursor", project_dir=tmp_path)

        install_dir = tmp_path / ".cursor" / "skills" / "nines"
        assert install_dir.exists()

        removed = installer.uninstall("cursor", project_dir=tmp_path)
        assert len(removed) > 0
        assert not install_dir.exists()
