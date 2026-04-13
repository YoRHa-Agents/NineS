"""Tests for the ``nines update`` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner
from packaging.version import Version

from nines import __version__

if TYPE_CHECKING:
    from pathlib import Path
from nines.cli.commands.update import (
    _current_version,
    _detect_installer,
    _fetch_latest_from_github,
    _fetch_latest_from_pypi,
    _fetch_latest_version,
)
from nines.cli.main import cli


class TestCurrentVersion:
    def test_returns_version_object(self) -> None:
        v = _current_version()
        assert isinstance(v, Version)
        assert str(v) == __version__


class TestFetchLatestFromPyPI:
    def test_returns_version_on_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"info": {"version": "2.0.0"}}
        mock_resp.raise_for_status = MagicMock()

        with patch("nines.cli.commands.update.httpx.get", return_value=mock_resp):
            result = _fetch_latest_from_pypi()
        assert result == Version("2.0.0")

    def test_returns_none_on_http_error(self) -> None:
        with patch(
            "nines.cli.commands.update.httpx.get",
            side_effect=httpx.ConnectError("offline"),
        ):
            result = _fetch_latest_from_pypi()
        assert result is None

    def test_returns_none_on_bad_json(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"bad": "data"}
        mock_resp.raise_for_status = MagicMock()

        with patch("nines.cli.commands.update.httpx.get", return_value=mock_resp):
            result = _fetch_latest_from_pypi()
        assert result is None


class TestFetchLatestFromGitHub:
    def test_returns_version_on_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "v3.1.0"}
        mock_resp.raise_for_status = MagicMock()

        with patch("nines.cli.commands.update.httpx.get", return_value=mock_resp):
            result = _fetch_latest_from_github()
        assert result == Version("3.1.0")

    def test_strips_v_prefix(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "V2.5.0"}
        mock_resp.raise_for_status = MagicMock()

        with patch("nines.cli.commands.update.httpx.get", return_value=mock_resp):
            result = _fetch_latest_from_github()
        assert result == Version("2.5.0")

    def test_returns_none_on_http_error(self) -> None:
        with patch(
            "nines.cli.commands.update.httpx.get",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            result = _fetch_latest_from_github()
        assert result is None


class TestFetchLatestVersion:
    def test_prefers_pypi(self) -> None:
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_from_pypi",
                return_value=Version("2.0.0"),
            ),
            patch(
                "nines.cli.commands.update._fetch_latest_from_github",
                return_value=Version("1.9.0"),
            ),
        ):
            result = _fetch_latest_version()
        assert result == Version("2.0.0")

    def test_falls_back_to_github(self) -> None:
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_from_pypi",
                return_value=None,
            ),
            patch(
                "nines.cli.commands.update._fetch_latest_from_github",
                return_value=Version("1.8.0"),
            ),
        ):
            result = _fetch_latest_version()
        assert result == Version("1.8.0")

    def test_returns_none_when_both_fail(self) -> None:
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_from_pypi",
                return_value=None,
            ),
            patch(
                "nines.cli.commands.update._fetch_latest_from_github",
                return_value=None,
            ),
        ):
            result = _fetch_latest_version()
        assert result is None


class TestDetectInstaller:
    def test_prefers_uv(self) -> None:
        with patch("nines.cli.commands.update.shutil.which", return_value="/usr/bin/uv"):
            assert _detect_installer() == "uv"

    def test_falls_back_to_pip(self) -> None:
        with patch("nines.cli.commands.update.shutil.which", return_value=None):
            assert _detect_installer() == "pip"


class TestUpdateCommandCLI:
    def test_update_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["update", "--help"])
        assert result.exit_code == 0
        assert "--check" in result.output
        assert "--skip-skills" in result.output
        assert "--target" in result.output
        assert "--global" in result.output

    def test_update_check_up_to_date(self) -> None:
        runner = CliRunner()
        with patch(
            "nines.cli.commands.update._fetch_latest_version",
            return_value=_current_version(),
        ):
            result = runner.invoke(cli, ["update", "--check"])
        assert result.exit_code == 0
        assert "up-to-date" in result.output

    def test_update_check_shows_available(self) -> None:
        runner = CliRunner()
        with patch(
            "nines.cli.commands.update._fetch_latest_version",
            return_value=Version("99.0.0"),
        ):
            result = runner.invoke(cli, ["update", "--check"])
        assert result.exit_code == 0
        assert "99.0.0" in result.output
        assert "Update available" in result.output

    def test_update_network_failure(self) -> None:
        runner = CliRunner()
        with patch(
            "nines.cli.commands.update._fetch_latest_version",
            return_value=None,
        ):
            result = runner.invoke(cli, ["update"])
        assert result.exit_code != 0
        assert "unable to check" in result.output

    def test_update_performs_upgrade(self) -> None:
        runner = CliRunner()
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_version",
                return_value=Version("99.0.0"),
            ),
            patch(
                "nines.cli.commands.update._run_upgrade",
                return_value=True,
            ) as mock_upgrade,
            patch(
                "nines.cli.commands.update._refresh_skills",
                return_value=["file1.md"],
            ),
        ):
            result = runner.invoke(cli, ["update"])
        assert result.exit_code == 0
        assert "Successfully upgraded" in result.output
        mock_upgrade.assert_called_once()

    def test_update_skip_skills(self) -> None:
        runner = CliRunner()
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_version",
                return_value=Version("99.0.0"),
            ),
            patch(
                "nines.cli.commands.update._run_upgrade",
                return_value=True,
            ),
            patch(
                "nines.cli.commands.update._refresh_skills",
            ) as mock_refresh,
        ):
            result = runner.invoke(cli, ["update", "--skip-skills"])
        assert result.exit_code == 0
        mock_refresh.assert_not_called()

    def test_update_upgrade_failure(self) -> None:
        runner = CliRunner()
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_version",
                return_value=Version("99.0.0"),
            ),
            patch(
                "nines.cli.commands.update._run_upgrade",
                return_value=False,
            ),
        ):
            result = runner.invoke(cli, ["update"])
        assert result.exit_code != 0
        assert "upgrade failed" in result.output

    def test_update_global_refreshes_to_home(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            patch(
                "nines.cli.commands.update._fetch_latest_version",
                return_value=Version("99.0.0"),
            ),
            patch(
                "nines.cli.commands.update._run_upgrade",
                return_value=True,
            ),
            patch(
                "nines.cli.commands.install.Path.home",
                return_value=tmp_path,
            ),
        ):
            result = runner.invoke(cli, ["update", "--global", "--target", "cursor"])
        assert result.exit_code == 0
        assert "global" in result.output
        assert (tmp_path / ".cursor" / "skills" / "nines" / "SKILL.md").exists()
