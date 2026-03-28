"""Tests for autoboot.flash module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from autoboot.flash import find_latest_iso, flash_iso, flash_machine, validate_device


class TestFindLatestIso:
    def test_finds_latest(self, tmp_path: Path):
        (tmp_path / "web-server-20240101.iso").touch()
        (tmp_path / "web-server-20240315.iso").touch()
        (tmp_path / "web-server-20240210.iso").touch()

        result = find_latest_iso("web-server", tmp_path)
        assert result is not None
        assert result.name == "web-server-20240315.iso"

    def test_returns_none_when_empty(self, tmp_path: Path):
        result = find_latest_iso("web-server", tmp_path)
        assert result is None

    def test_ignores_other_machines(self, tmp_path: Path):
        (tmp_path / "other-machine-20240101.iso").touch()
        result = find_latest_iso("web-server", tmp_path)
        assert result is None

    def test_single_iso(self, tmp_path: Path):
        (tmp_path / "db-01-20240501.iso").touch()
        result = find_latest_iso("db-01", tmp_path)
        assert result is not None
        assert result.name == "db-01-20240501.iso"


class TestValidateDevice:
    def test_nonexistent_device(self):
        errors = validate_device(Path("/dev/nonexistent_device_xyz"))
        assert any("not found" in e.lower() for e in errors)

    def test_not_block_device(self, tmp_path: Path):
        regular_file = tmp_path / "not_a_device"
        regular_file.touch()
        errors = validate_device(regular_file)
        assert any("not a block device" in e.lower() for e in errors)

    def test_refuses_sda(self):
        errors = validate_device(Path("/dev/sda"))
        assert any("system drive" in e.lower() for e in errors)

    def test_refuses_nvme0n1(self):
        errors = validate_device(Path("/dev/nvme0n1"))
        assert any("system drive" in e.lower() for e in errors)

    def test_refuses_vda(self):
        errors = validate_device(Path("/dev/vda"))
        assert any("system drive" in e.lower() for e in errors)


class TestFlashIso:
    def test_raises_if_iso_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="ISO not found"):
            flash_iso(
                tmp_path / "missing.iso",
                Path("/dev/sdb"),
                tmp_path,
            )

    def test_raises_if_device_invalid(self, tmp_path: Path):
        iso = tmp_path / "test.iso"
        iso.write_bytes(b"fake")
        not_device = tmp_path / "not_a_device"
        not_device.touch()

        with pytest.raises(ValueError, match="Not a block device"):
            flash_iso(iso, not_device, tmp_path)

    @patch("autoboot.flash.validate_device", return_value=[])
    @patch("autoboot.flash.subprocess.run")
    def test_calls_flash_script(self, mock_run, _mock_validate, tmp_path: Path):
        iso = tmp_path / "test.iso"
        iso.write_bytes(b"fake")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "flash-usb.sh").write_text("#!/bin/bash\necho ok")
        device = Path("/dev/sdb")

        flash_iso(iso, device, scripts_dir)

        assert mock_run.called
        call_args = mock_run.call_args[0][0]
        assert str(scripts_dir / "flash-usb.sh") in call_args
        assert "--iso" in call_args
        assert "--device" in call_args

    @patch("autoboot.flash.validate_device", return_value=[])
    @patch("autoboot.flash.subprocess.run")
    def test_passes_yes_flag(self, mock_run, _mock_validate, tmp_path: Path):
        iso = tmp_path / "test.iso"
        iso.write_bytes(b"fake")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "flash-usb.sh").touch()

        flash_iso(iso, Path("/dev/sdb"), scripts_dir, skip_confirm=True)

        call_args = mock_run.call_args[0][0]
        assert "--yes" in call_args


class TestFlashMachine:
    @patch("autoboot.flash.subprocess.run")
    @patch("autoboot.flash.validate_device", return_value=[])
    def test_finds_and_flashes(self, _mock_validate, mock_run, tmp_path: Path):
        # Set up project structure
        built_dir = tmp_path / "isos" / "built"
        built_dir.mkdir(parents=True)
        (built_dir / "web-01-20240301.iso").write_bytes(b"fake")
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "flash-usb.sh").touch()

        with patch("autoboot.flash.get_built_dir", return_value=built_dir), \
             patch("autoboot.flash.get_scripts_dir", return_value=scripts_dir):
            flash_machine("web-01", Path("/dev/sdb"), root=tmp_path)

        assert mock_run.called

    def test_raises_when_no_iso(self, tmp_path: Path):
        built_dir = tmp_path / "isos" / "built"
        built_dir.mkdir(parents=True)
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        with patch("autoboot.flash.get_built_dir", return_value=built_dir), \
             patch("autoboot.flash.get_scripts_dir", return_value=scripts_dir):
            with pytest.raises(FileNotFoundError, match="No built ISO found"):
                flash_machine("nonexistent", Path("/dev/sdb"), root=tmp_path)
