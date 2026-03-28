"""Tests for autoboot.cli module."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from autoboot.cli import main


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def project_root(tmp_path: Path):
    """Set up a minimal project structure."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    (keys_dir / "ansible.pub").write_text("ssh-ed25519 TESTKEY user@host")
    (tmp_path / "isos" / "downloads").mkdir(parents=True)
    (tmp_path / "isos" / "built").mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    (tmp_path / "scripts").mkdir()
    return tmp_path


class TestMainGroup:
    def test_help(self, runner: CliRunner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "autoboot" in result.output.lower() or "Usage" in result.output

    def test_version(self, runner: CliRunner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestListCommand:
    def test_list_no_configs(self, runner: CliRunner, project_root: Path):
        result = runner.invoke(main, ["list", "--root", str(project_root)])
        assert result.exit_code == 0
        assert "No machine configs found" in result.output

    def test_list_with_configs(self, runner: CliRunner, project_root: Path):
        configs_dir = project_root / "configs"
        (configs_dir / "web-01").mkdir()
        (configs_dir / "web-01" / "config.yaml").write_text(
            "machine_name: web-01\ndistro: ubuntu\n"
        )
        (configs_dir / "db-01").mkdir()
        (configs_dir / "db-01" / "config.yaml").write_text(
            "machine_name: db-01\ndistro: debian\n"
        )

        result = runner.invoke(main, ["list", "--root", str(project_root)])
        assert result.exit_code == 0
        assert "web-01" in result.output
        assert "db-01" in result.output


class TestNewCommand:
    def test_creates_config(self, runner: CliRunner, project_root: Path):
        result = runner.invoke(
            main,
            ["new", "test-server", "--distro", "ubuntu", "--root", str(project_root)],
        )
        assert result.exit_code == 0
        config_file = project_root / "configs" / "test-server" / "config.yaml"
        assert config_file.exists()

    def test_with_version(self, runner: CliRunner, project_root: Path):
        result = runner.invoke(
            main,
            [
                "new", "test-server",
                "--distro", "ubuntu",
                "--version", "24.04.1",
                "--root", str(project_root),
            ],
        )
        assert result.exit_code == 0
        content = (
            project_root / "configs" / "test-server" / "config.yaml"
        ).read_text()
        assert "24.04.1" in content

    def test_refuses_existing(self, runner: CliRunner, project_root: Path):
        config_dir = project_root / "configs" / "existing"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("machine_name: existing\n")

        result = runner.invoke(
            main,
            ["new", "existing", "--distro", "ubuntu", "--root", str(project_root)],
        )
        assert result.exit_code != 0
        assert "already exists" in result.output


class TestValidateCommand:
    def test_valid_config(self, runner: CliRunner, project_root: Path):
        config_dir = project_root / "configs" / "test-server"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "machine_name: test-server\n"
            "distro: ubuntu\n"
            "distro_version: '24.04.3'\n"
            "admin:\n"
            "  username: admin\n"
            "  password_hash: '$6$hash'\n"
        )

        result = runner.invoke(
            main, ["validate", "test-server", "--root", str(project_root)]
        )
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_missing_config(self, runner: CliRunner, project_root: Path):
        result = runner.invoke(
            main, ["validate", "nonexistent", "--root", str(project_root)]
        )
        assert result.exit_code != 0


class TestDownloadCommand:
    @patch("autoboot.cli.download_iso")
    def test_download(self, mock_download, runner: CliRunner, project_root: Path):
        config_dir = project_root / "configs" / "test-server"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "machine_name: test-server\n"
            "distro: ubuntu\n"
            "distro_version: '24.04.3'\n"
            "admin:\n"
            "  username: admin\n"
            "  password_hash: '$6$hash'\n"
        )
        mock_download.return_value = Path("/fake/path.iso")

        result = runner.invoke(
            main, ["download", "test-server", "--root", str(project_root)]
        )
        assert result.exit_code == 0
        assert mock_download.called

    @patch("autoboot.cli.download_iso")
    def test_download_with_force(
        self, mock_download, runner: CliRunner, project_root: Path,
    ):
        config_dir = project_root / "configs" / "test-server"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "machine_name: test-server\n"
            "distro: ubuntu\n"
            "distro_version: '24.04.3'\n"
            "admin:\n"
            "  username: admin\n"
            "  password_hash: '$6$hash'\n"
        )
        mock_download.return_value = Path("/fake/path.iso")

        result = runner.invoke(
            main,
            ["download", "test-server", "--force", "--root", str(project_root)],
        )
        assert result.exit_code == 0
        _, kwargs = mock_download.call_args
        assert kwargs.get("force") is True


class TestBuildCommand:
    @patch("autoboot.cli.build_machine")
    def test_build(self, mock_build, runner: CliRunner, project_root: Path):
        mock_build.return_value = Path("/fake/output.iso")

        result = runner.invoke(
            main, ["build", "test-server", "--root", str(project_root)]
        )
        assert result.exit_code == 0
        assert mock_build.called


class TestFlashCommand:
    @patch("autoboot.cli.flash_machine")
    def test_flash(self, mock_flash, runner: CliRunner, project_root: Path):
        result = runner.invoke(
            main,
            ["flash", "test-server", "/dev/sdb", "--root", str(project_root)],
        )
        assert result.exit_code == 0
        assert mock_flash.called

    @patch("autoboot.cli.flash_machine")
    def test_flash_with_yes(self, mock_flash, runner: CliRunner, project_root: Path):
        result = runner.invoke(
            main,
            [
                "flash", "test-server", "/dev/sdb",
                "--yes", "--root", str(project_root),
            ],
        )
        assert result.exit_code == 0
        _, kwargs = mock_flash.call_args
        assert kwargs.get("skip_confirm") is True
