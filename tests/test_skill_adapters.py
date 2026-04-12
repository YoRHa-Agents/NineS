"""Tests for cursor_adapter and claude_adapter skill file generation."""

from __future__ import annotations

from pathlib import Path

from nines.skill.claude_adapter import ClaudeAdapter
from nines.skill.cursor_adapter import CursorAdapter
from nines.skill.installer import SkillInstaller
from nines.skill.manifest import SkillManifest


class TestCursorSkillMdGenerated:
    """CursorAdapter.generate_skill_dir creates SKILL.md with valid content."""

    def test_cursor_skill_md_generated(self, tmp_path: Path) -> None:
        adapter = CursorAdapter()
        written = adapter.generate_skill_dir(tmp_path)

        skill_md = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        assert skill_md.exists(), "SKILL.md was not created"
        assert skill_md in written

        content = skill_md.read_text(encoding="utf-8")
        assert "# NINES" in content
        assert "Available Commands" in content
        assert "nines-eval" in content
        assert "Prerequisites" in content

    def test_cursor_skill_md_has_all_commands(self, tmp_path: Path) -> None:
        adapter = CursorAdapter()
        adapter.generate_skill_dir(tmp_path)

        skill_md = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        for cmd_name in ("nines-eval", "nines-collect", "nines-analyze",
                         "nines-self-eval", "nines-iterate", "nines-install"):
            assert cmd_name in content, f"{cmd_name} missing from SKILL.md"

    def test_cursor_generates_command_workflow_files(self, tmp_path: Path) -> None:
        adapter = CursorAdapter()
        written = adapter.generate_skill_dir(tmp_path)

        commands_dir = tmp_path / ".cursor" / "skills" / "nines" / "commands"
        assert commands_dir.is_dir()
        assert (commands_dir / "eval.md").exists()
        assert (commands_dir / "collect.md").exists()
        assert (commands_dir / "analyze.md").exists()
        assert len(written) == 7  # SKILL.md + 6 commands

    def test_cursor_custom_manifest(self, tmp_path: Path) -> None:
        manifest = SkillManifest(name="custom-nines", description="Custom NineS")
        adapter = CursorAdapter()
        adapter.generate_skill_dir(tmp_path, manifest=manifest)

        content = (tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md").read_text()
        assert "CUSTOM-NINES" in content
        assert "Custom NineS" in content


class TestClaudeCommandsGenerated:
    """ClaudeAdapter.generate_commands creates slash command .md files."""

    def test_claude_commands_generated(self, tmp_path: Path) -> None:
        adapter = ClaudeAdapter()
        written = adapter.generate_commands(tmp_path)

        assert len(written) == 6

        eval_md = tmp_path / ".claude" / "commands" / "nines" / "eval.md"
        assert eval_md.exists(), "eval.md was not created"
        assert eval_md in written

        content = eval_md.read_text(encoding="utf-8")
        assert "nines:eval" in content
        assert "allowed-tools" in content

    def test_claude_all_command_files_present(self, tmp_path: Path) -> None:
        adapter = ClaudeAdapter()
        adapter.generate_commands(tmp_path)

        base = tmp_path / ".claude" / "commands" / "nines"
        for name in ("eval.md", "collect.md", "analyze.md",
                     "self-eval.md", "iterate.md", "install.md"):
            assert (base / name).exists(), f"{name} missing"

    def test_claude_command_frontmatter(self, tmp_path: Path) -> None:
        adapter = ClaudeAdapter()
        adapter.generate_commands(tmp_path)

        content = (
            tmp_path / ".claude" / "commands" / "nines" / "collect.md"
        ).read_text()
        assert content.startswith("---")
        assert "nines:collect" in content
        assert "description:" in content
        assert "argument-hint:" in content

    def test_claude_excludes_virtual_section(self, tmp_path: Path) -> None:
        adapter = ClaudeAdapter()
        written = adapter.generate_commands(tmp_path)
        paths = [p.name for p in written]
        assert "__CLAUDE_MD_SECTION__" not in paths


class TestInstallCursor:
    """SkillInstaller integration with Cursor target using real adapters."""

    def test_install_cursor(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("cursor", project_dir=tmp_path)

        assert len(created) > 0

        skill_md = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text(encoding="utf-8")
        assert "NINES" in content
        assert "Available Commands" in content

    def test_install_cursor_creates_command_dirs(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        installer.install("cursor", project_dir=tmp_path)

        commands_dir = tmp_path / ".cursor" / "skills" / "nines" / "commands"
        assert commands_dir.is_dir()
        assert (commands_dir / "eval.md").exists()


class TestInstallClaude:
    """SkillInstaller integration with Claude target using real adapters."""

    def test_install_claude(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("claude", project_dir=tmp_path)

        assert len(created) > 0

        eval_md = tmp_path / ".claude" / "commands" / "nines" / "eval.md"
        assert eval_md.exists()
        content = eval_md.read_text(encoding="utf-8")
        assert "nines:eval" in content

    def test_install_all_creates_both(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("all", project_dir=tmp_path)

        cursor_skill = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        claude_eval = tmp_path / ".claude" / "commands" / "nines" / "eval.md"
        assert cursor_skill.exists()
        assert claude_eval.exists()
        assert len(created) > 0
