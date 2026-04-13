"""Tests for skill file generation across all adapters."""

from __future__ import annotations

from pathlib import Path

from nines.skill.claude_adapter import ClaudeAdapter
from nines.skill.codex_adapter import CodexAdapter
from nines.skill.copilot_adapter import CopilotAdapter
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
                         "nines-self-eval", "nines-iterate", "nines-install",
                         "nines-update"):
            assert cmd_name in content, f"{cmd_name} missing from SKILL.md"

    def test_cursor_generates_command_workflow_files(self, tmp_path: Path) -> None:
        adapter = CursorAdapter()
        written = adapter.generate_skill_dir(tmp_path)

        commands_dir = tmp_path / ".cursor" / "skills" / "nines" / "commands"
        assert commands_dir.is_dir()
        assert (commands_dir / "eval.md").exists()
        assert (commands_dir / "collect.md").exists()
        assert (commands_dir / "analyze.md").exists()
        assert len(written) == 8  # SKILL.md + 7 commands

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

        assert len(written) == 7

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
                     "self-eval.md", "iterate.md", "install.md", "update.md"):
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

    def test_install_all_creates_all_four(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("all", project_dir=tmp_path)

        cursor_skill = tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md"
        claude_eval = tmp_path / ".claude" / "commands" / "nines" / "eval.md"
        codex_skill = tmp_path / ".codex" / "skills" / "nines" / "SKILL.md"
        copilot_inst = tmp_path / ".github" / "copilot-instructions.md"
        assert cursor_skill.exists()
        assert claude_eval.exists()
        assert codex_skill.exists()
        assert copilot_inst.exists()
        assert len(created) > 0


class TestCodexSkillMdGenerated:
    """CodexAdapter.generate_skill_dir creates SKILL.md with valid content."""

    def test_codex_skill_md_generated(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        written = adapter.generate_skill_dir(tmp_path)

        skill_md = tmp_path / ".codex" / "skills" / "nines" / "SKILL.md"
        assert skill_md.exists(), "SKILL.md was not created"
        assert skill_md in written

        content = skill_md.read_text(encoding="utf-8")
        assert "# NINES" in content
        assert "Available Commands" in content
        assert "Prerequisites" in content

    def test_codex_skill_md_has_frontmatter(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        adapter.generate_skill_dir(tmp_path)

        skill_md = tmp_path / ".codex" / "skills" / "nines" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "name: nines" in content
        assert "description:" in content
        assert "version:" in content
        assert "author:" in content

    def test_codex_skill_md_has_all_commands(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        adapter.generate_skill_dir(tmp_path)

        skill_md = tmp_path / ".codex" / "skills" / "nines" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        for short in ("eval", "collect", "analyze", "self-eval", "iterate", "install", "update"):
            assert short in content, f"{short} missing from SKILL.md"

    def test_codex_generates_command_workflow_files(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        written = adapter.generate_skill_dir(tmp_path)

        commands_dir = tmp_path / ".codex" / "skills" / "nines" / "commands"
        assert commands_dir.is_dir()
        assert (commands_dir / "eval.md").exists()
        assert (commands_dir / "collect.md").exists()
        assert (commands_dir / "analyze.md").exists()
        assert (commands_dir / "self-eval.md").exists()
        assert (commands_dir / "iterate.md").exists()
        assert (commands_dir / "install.md").exists()
        assert (commands_dir / "update.md").exists()
        assert len(written) == 8  # SKILL.md + 7 commands

    def test_codex_command_file_content(self, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        adapter.generate_skill_dir(tmp_path)

        eval_md = tmp_path / ".codex" / "skills" / "nines" / "commands" / "eval.md"
        content = eval_md.read_text(encoding="utf-8")
        assert "# nines-eval" in content
        assert "Invocation" in content
        assert "nines eval" in content
        assert "Capability: `eval`" in content

    def test_codex_custom_manifest(self, tmp_path: Path) -> None:
        manifest = SkillManifest(name="custom-nines", description="Custom NineS")
        adapter = CodexAdapter()
        adapter.generate_skill_dir(tmp_path, manifest=manifest)

        content = (tmp_path / ".codex" / "skills" / "nines" / "SKILL.md").read_text()
        assert "CUSTOM-NINES" in content
        assert "Custom NineS" in content
        assert "name: custom-nines" in content

    def test_codex_emit_returns_seven_files(self) -> None:
        from nines.skill.adapters import CodexAdapter as BaseCodexAdapter

        adapter = BaseCodexAdapter()
        manifest = SkillManifest()
        files = adapter.emit(manifest)
        assert len(files) == 8
        assert files[0].relative_path == "SKILL.md"
        for f in files[1:]:
            assert f.relative_path.startswith("commands/")

    def test_codex_satisfies_skill_adapter_protocol(self) -> None:
        from nines.skill.adapters import CodexAdapter as BaseCodexAdapter, SkillAdapter

        adapter = BaseCodexAdapter()
        assert isinstance(adapter, SkillAdapter)
        assert adapter.runtime_name == "codex"


class TestCopilotInstructionsGenerated:
    """CopilotAdapter.generate_instructions creates copilot-instructions.md."""

    def test_copilot_instructions_generated(self, tmp_path: Path) -> None:
        adapter = CopilotAdapter()
        written = adapter.generate_instructions(tmp_path)

        assert written.exists(), "copilot-instructions.md was not created"
        content = written.read_text(encoding="utf-8")
        assert "NINES" in content
        assert "Available Commands" in content

    def test_copilot_emits_single_file(self) -> None:
        from nines.skill.adapters import CopilotAdapter as BaseCopilotAdapter

        adapter = BaseCopilotAdapter()
        files = adapter.emit(SkillManifest())
        assert len(files) == 1
        assert files[0].relative_path == "copilot-instructions.md"

    def test_copilot_has_all_commands(self, tmp_path: Path) -> None:
        adapter = CopilotAdapter()
        written = adapter.generate_instructions(tmp_path)
        content = written.read_text(encoding="utf-8")
        for short in ("eval", "collect", "analyze", "self-eval", "iterate", "install", "update"):
            assert short in content, f"{short} missing from copilot-instructions.md"

    def test_copilot_has_prerequisites(self, tmp_path: Path) -> None:
        adapter = CopilotAdapter()
        written = adapter.generate_instructions(tmp_path)
        content = written.read_text(encoding="utf-8")
        assert "Prerequisites" in content
        assert "nines" in content

    def test_copilot_custom_manifest(self, tmp_path: Path) -> None:
        manifest = SkillManifest(name="custom-nines", description="Custom NineS")
        adapter = CopilotAdapter()
        written = adapter.generate_instructions(tmp_path, manifest=manifest)
        content = written.read_text(encoding="utf-8")
        assert "CUSTOM-NINES" in content
        assert "Custom NineS" in content

    def test_copilot_satisfies_skill_adapter_protocol(self) -> None:
        from nines.skill.adapters import CopilotAdapter as BaseCopilotAdapter, SkillAdapter

        adapter = BaseCopilotAdapter()
        assert isinstance(adapter, SkillAdapter)
        assert adapter.runtime_name == "copilot"


class TestInstallCodex:
    """SkillInstaller integration with Codex target."""

    def test_install_codex(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("codex", project_dir=tmp_path)

        assert len(created) > 0
        skill_md = tmp_path / ".codex" / "skills" / "nines" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text(encoding="utf-8")
        assert "NINES" in content

    def test_uninstall_codex(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        installer.install("codex", project_dir=tmp_path)
        removed = installer.uninstall("codex", project_dir=tmp_path)
        assert len(removed) == 1
        assert not (tmp_path / ".codex" / "skills" / "nines").exists()


class TestInstallCopilot:
    """SkillInstaller integration with Copilot target."""

    def test_install_copilot(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("copilot", project_dir=tmp_path)

        assert len(created) == 1
        instructions = tmp_path / ".github" / "copilot-instructions.md"
        assert instructions.exists()
        content = instructions.read_text(encoding="utf-8")
        assert "NINES" in content

    def test_uninstall_copilot(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        installer.install("copilot", project_dir=tmp_path)
        removed = installer.uninstall("copilot", project_dir=tmp_path)
        assert len(removed) == 1


class TestInstallAll:
    """SkillInstaller integration with 'all' target across all runtimes."""

    def test_install_all_creates_four_runtimes(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        created = installer.install("all", project_dir=tmp_path)

        assert (tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md").exists()
        assert (tmp_path / ".claude" / "commands" / "nines" / "eval.md").exists()
        assert (tmp_path / ".codex" / "skills" / "nines" / "SKILL.md").exists()
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()
        assert len(created) > 10

    def test_uninstall_all(self, tmp_path: Path) -> None:
        installer = SkillInstaller()
        installer.install("all", project_dir=tmp_path)
        removed = installer.uninstall("all", project_dir=tmp_path)
        assert len(removed) == 4
