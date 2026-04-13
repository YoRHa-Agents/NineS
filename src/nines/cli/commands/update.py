"""``nines update`` — check for and install NineS updates."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

import click
import httpx
from packaging.version import InvalidVersion, Version

from nines import __version__

logger = logging.getLogger(__name__)

_PYPI_URL = "https://pypi.org/pypi/nines/json"
_GITHUB_URL = "https://api.github.com/repos/YoRHa-Agents/NineS/releases/latest"
_REQUEST_TIMEOUT = 15


def _current_version() -> Version:
    return Version(__version__)


def _fetch_latest_from_pypi() -> Version | None:
    """Query PyPI for the latest published version."""
    try:
        resp = httpx.get(_PYPI_URL, timeout=_REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        return Version(data["info"]["version"])
    except (httpx.HTTPError, KeyError, InvalidVersion) as exc:
        logger.debug("PyPI check failed: %s", exc)
        return None


def _fetch_latest_from_github() -> Version | None:
    """Fallback: query GitHub releases API for the latest tag."""
    try:
        resp = httpx.get(
            _GITHUB_URL,
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        tag: str = resp.json()["tag_name"]
        return Version(tag.lstrip("vV"))
    except (httpx.HTTPError, KeyError, InvalidVersion) as exc:
        logger.debug("GitHub check failed: %s", exc)
        return None


def _fetch_latest_version() -> Version | None:
    """Return the latest upstream version, trying PyPI first then GitHub."""
    version = _fetch_latest_from_pypi()
    if version is not None:
        return version
    return _fetch_latest_from_github()


def _detect_installer() -> str:
    """Return ``'uv'`` if uv is available, otherwise ``'pip'``."""
    if shutil.which("uv") is not None:
        return "uv"
    return "pip"


def _run_upgrade(installer: str) -> bool:
    """Execute the actual package upgrade. Returns True on success."""
    if installer == "uv":
        cmd = [installer, "pip", "install", "--upgrade", "nines"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "nines"]

    logger.info("Running upgrade: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603

    if result.returncode != 0:
        logger.error("Upgrade command failed (exit %d): %s", result.returncode, result.stderr)
        return False

    logger.debug("Upgrade stdout: %s", result.stdout)
    return True


def _refresh_skills(target: str, project_dir: Path) -> list[str]:
    """Re-run skill installation to regenerate skill files."""
    from nines.skill.installer import SkillInstaller

    installer = SkillInstaller()
    return installer.install(target, project_dir=project_dir)


@click.command("update")
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    default=False,
    help="Only check if an update is available, don't install.",
)
@click.option(
    "--skip-skills",
    is_flag=True,
    default=False,
    help="Skip skill file refresh after update.",
)
@click.option(
    "--target",
    type=click.Choice(
        ["cursor", "claude", "codex", "copilot", "all"], case_sensitive=False
    ),
    default="all",
    help="Which skill targets to refresh (default: all).",
)
@click.pass_context
def update_cmd(
    ctx: click.Context,
    check_only: bool,
    skip_skills: bool,
    target: str,
) -> None:
    """Check for and install NineS updates, refresh skill files."""
    verbose = ctx.obj.get("verbose", False)
    current = _current_version()

    if verbose:
        click.echo(f"Current version: {current}")

    click.echo("Checking for updates…")
    latest = _fetch_latest_version()

    if latest is None:
        logger.error("Could not determine the latest version from PyPI or GitHub.")
        click.echo("Error: unable to check for updates (network issue or API unavailable).")
        ctx.exit(1)
        return

    if verbose:
        click.echo(f"Latest version:  {latest}")

    if latest <= current:
        click.echo(f"NineS is already up-to-date (v{current}).")
        return

    click.echo(f"Update available: v{current} → v{latest}")

    if check_only:
        return

    installer_name = _detect_installer()
    if verbose:
        click.echo(f"Using installer: {installer_name}")

    click.echo(f"Upgrading NineS via {installer_name}…")
    success = _run_upgrade(installer_name)

    if not success:
        click.echo("Error: upgrade failed. Check the logs for details.")
        ctx.exit(1)
        return

    click.echo(f"Successfully upgraded to v{latest}.")

    if skip_skills:
        if verbose:
            click.echo("Skipping skill refresh (--skip-skills).")
        return

    click.echo(f"Refreshing skill files for target={target}…")
    project_dir = Path.cwd()

    try:
        created = _refresh_skills(target, project_dir)
        click.echo(f"Refreshed {len(created)} skill file(s):")
        for path in created:
            click.echo(f"  {path}")
    except Exception:
        logger.exception("Skill refresh failed")
        click.echo("Warning: skill refresh failed. You can retry with: nines install --target all")
