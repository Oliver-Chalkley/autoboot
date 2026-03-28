"""Tests for autoboot.build module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from autoboot.build import build_iso, check_build_prerequisites, render_installer_config
from autoboot.models import AdminConfig, MachineConfig

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def make_config(**overrides) -> MachineConfig:
    defaults = {
        "machine_name": "test-server",
        "distro": "ubuntu",
        "distro_version": "24.04.3",
        "admin": AdminConfig(username="admin", password_hash="$6$hash"),
    }
    defaults.update(overrides)
    return MachineConfig(**defaults)


class TestCheckBuildPrerequisites:
    def test_passes_when_xorriso_available(self):
        with patch("autoboot.build.shutil.which", return_value="/usr/bin/xorriso"):
            check_build_prerequisites()  # should not raise

    def test_raises_when_xorriso_missing(self):
        with patch("autoboot.build.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="xorriso is not installed"):
                check_build_prerequisites()

    def test_error_message_includes_install_instructions(self):
        with patch("autoboot.build.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="sudo apt install xorriso"):
                check_build_prerequisites()


class TestRenderInstallerConfig:
    def test_renders_ubuntu_config(self):
        config = make_config()
        rendered = render_installer_config(
            config, "ssh-ed25519 KEY", TEMPLATES_DIR
        )
        assert "nocloud/user-data" in rendered
        assert "nocloud/meta-data" in rendered

    def test_renders_debian_config(self):
        config = make_config(distro="debian", distro_version="12.9")
        rendered = render_installer_config(
            config, "ssh-ed25519 KEY", TEMPLATES_DIR
        )
        assert "preseed.cfg" in rendered

    def test_invalid_render_raises(self):
        config = make_config()
        with patch("autoboot.distros.ubuntu.UbuntuHandler.render_config") as mock:
            mock.return_value = {}  # Missing user-data
            with pytest.raises(ValueError, match="validation failed"):
                render_installer_config(config, "key", TEMPLATES_DIR)


class TestBuildIso:
    @patch("autoboot.build.subprocess.run")
    def test_calls_build_script(self, mock_run, tmp_path: Path):
        config = make_config()
        source_iso = tmp_path / "source.iso"
        source_iso.write_bytes(b"fake iso")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build-iso.sh").write_text("#!/bin/bash\necho ok")
        output_dir = tmp_path / "output"

        build_iso(
            config, source_iso, "ssh-ed25519 KEY", TEMPLATES_DIR,
            scripts_dir, output_dir,
        )

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert str(scripts_dir / "build-iso.sh") in call_args
        assert "--source-iso" in call_args
        assert "--grub-sed" in call_args

    @patch("autoboot.build.subprocess.run")
    def test_output_filename_contains_machine_name(self, mock_run, tmp_path: Path):
        config = make_config(machine_name="prod-web-01")
        source_iso = tmp_path / "source.iso"
        source_iso.write_bytes(b"fake")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build-iso.sh").touch()
        output_dir = tmp_path / "output"

        result = build_iso(
            config, source_iso, "ssh-ed25519 KEY", TEMPLATES_DIR,
            scripts_dir, output_dir,
        )

        assert "prod-web-01" in result.name
        assert result.suffix == ".iso"

    @patch("autoboot.build.subprocess.run")
    def test_creates_output_directory(self, mock_run, tmp_path: Path):
        config = make_config()
        source_iso = tmp_path / "source.iso"
        source_iso.write_bytes(b"fake")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build-iso.sh").touch()
        output_dir = tmp_path / "deep" / "nested" / "output"

        build_iso(
            config, source_iso, "ssh-ed25519 KEY", TEMPLATES_DIR,
            scripts_dir, output_dir,
        )

        assert output_dir.exists()
