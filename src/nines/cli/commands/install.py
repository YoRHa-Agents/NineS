"""``nines install`` — install or uninstall NineS as an agent skill."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from nines.skill.installer import SkillInstaller

logger = logging.getLogger(__name__)


@click.command("install")
@click.option(
    "--target",
    required=True,
    type=click.Choice(
        ["cursor", "claude", "codex", "copilot", "all"], case_sensitive=False
    ),
    help="Runtime target for installation.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing skill files without prompting.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be installed without writing files.",
)
@click.option(
    "--uninstall",
    is_flag=True,
    default=False,
    help="Remove NineS skill from target.",
)
@click.pass_context
def install_cmd(
    ctx: click.Context,
    target: str,
    force: bool,
    dry_run: bool,
    uninstall: bool,
) -> None:
    """Install or uninstall NineS as an agent skill."""
    verbose = ctx.obj.get("verbose", False)

    installer = SkillInstaller()
    project_dir = Path.cwd()
    all_targets = ["cursor", "claude", "codex", "copilot"]

    if dry_run:
        action = "uninstall" if uninstall else "install"
        click.echo(f"Dry run: would {action} NineS skill for target={target}")
        targets = [target] if target != "all" else all_targets
        for t in targets:
            adapter = installer.ADAPTERS[t]
            from nines.skill.manifest import SkillManifest

            files = adapter.emit(SkillManifest())
            for f in files:
                if f.relative_path == "__CLAUDE_MD_SECTION__":
                    continue
                click.echo(f"  Would create: {f.relative_path}")
        return

    if uninstall:
        if verbose:
            click.echo(f"Uninstalling NineS skill for target={target}")
        removed = installer.uninstall(target, project_dir=project_dir)
        click.echo(f"Removed {len(removed)} directory(ies) for target={target}:")
        for path in removed:
            click.echo(f"  {path}")
        return

    if verbose:
        click.echo(f"Installing NineS skill for target={target}")

    created = installer.install(target, project_dir=project_dir)
    click.echo(f"Installed {len(created)} file(s) for target={target}:")
    for path in created:
        click.echo(f"  {path}")
