"""Tests for autoboot.test module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autoboot.test import (
    VmTestResult,
    check_test_prerequisites,
    get_packer_template,
    run_vm_test,
    verify_machine,
)


class TestCheckTestPrerequisites:
    def test_passes_when_all_available(self):
        with patch(
            "autoboot.test.shutil.which",
            side_effect=lambda x: f"/usr/bin/{x}",
        ):
            check_test_prerequisites()  # should not raise

    def test_raises_when_packer_missing(self):
        def which(name: str) -> str | None:
            return None if name == "packer" else f"/usr/bin/{name}"

        with patch("autoboot.test.shutil.which", side_effect=which):
            with pytest.raises(RuntimeError, match="packer"):
                check_test_prerequisites()

    def test_raises_when_qemu_missing(self):
        def which(name: str) -> str | None:
            return None if name == "qemu-system-x86_64" else f"/usr/bin/{name}"

        with patch("autoboot.test.shutil.which", side_effect=which):
            with pytest.raises(RuntimeError, match="qemu"):
                check_test_prerequisites()

    def test_raises_with_both_missing(self):
        with patch("autoboot.test.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="packer.*qemu|qemu.*packer"):
                check_test_prerequisites()


class TestGetPackerTemplate:
    def test_ubuntu_template(self, tmp_path: Path):
        e2e_dir = tmp_path / "tests" / "e2e"
        e2e_dir.mkdir(parents=True)
        template = e2e_dir / "ubuntu-autoinstall.pkr.hcl"
        template.touch()

        result = get_packer_template("ubuntu", tmp_path)
        assert result == template

    def test_debian_template(self, tmp_path: Path):
        e2e_dir = tmp_path / "tests" / "e2e"
        e2e_dir.mkdir(parents=True)
        template = e2e_dir / "debian-preseed.pkr.hcl"
        template.touch()

        result = get_packer_template("debian", tmp_path)
        assert result == template

    def test_fedora_template(self, tmp_path: Path):
        e2e_dir = tmp_path / "tests" / "e2e"
        e2e_dir.mkdir(parents=True)
        template = e2e_dir / "fedora-kickstart.pkr.hcl"
        template.touch()

        result = get_packer_template("fedora", tmp_path)
        assert result == template

    def test_unknown_distro(self, tmp_path: Path):
        with pytest.raises(ValueError, match="No test template"):
            get_packer_template("arch", tmp_path)

    def test_template_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="not found"):
            get_packer_template("ubuntu", tmp_path)


class TestRunVmTest:
    @patch("autoboot.test.subprocess.Popen")
    @patch("autoboot.test.subprocess.run")
    def test_returns_result_on_success(
        self, mock_run, mock_popen, tmp_path: Path,
    ):
        mock_process = MagicMock()
        mock_process.stdout = iter([
            "==> qemu.ubuntu: output\n",
            "All checks passed\n",
        ])
        mock_process.returncode = 0
        mock_process.args = ["packer", "build"]
        mock_popen.return_value = mock_process

        result = run_vm_test(
            iso_path=tmp_path / "test.iso",
            template=tmp_path / "template.pkr.hcl",
            ssh_key_path=tmp_path / "key",
            project_root=tmp_path,
        )

        assert isinstance(result, VmTestResult)
        assert result.passed is True
        assert "All checks passed" in result.output
        assert result.duration > 0

    @patch("autoboot.test.subprocess.Popen")
    @patch("autoboot.test.subprocess.run")
    def test_returns_result_on_failure(
        self, mock_run, mock_popen, tmp_path: Path,
    ):
        mock_process = MagicMock()
        mock_process.stdout = iter(["Error: something went wrong\n"])
        mock_process.returncode = 1
        mock_process.args = ["packer", "build"]
        mock_popen.return_value = mock_process

        result = run_vm_test(
            iso_path=tmp_path / "test.iso",
            template=tmp_path / "template.pkr.hcl",
            ssh_key_path=tmp_path / "key",
            project_root=tmp_path,
        )

        assert result.passed is False

    @patch("autoboot.test.subprocess.Popen")
    @patch("autoboot.test.subprocess.run")
    def test_passes_correct_packer_args(
        self, mock_run, mock_popen, tmp_path: Path,
    ):
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.returncode = 0
        mock_process.args = ["packer", "build"]
        mock_popen.return_value = mock_process

        iso = tmp_path / "my-server.iso"
        template = tmp_path / "ubuntu.pkr.hcl"
        key = tmp_path / "ansible"

        run_vm_test(iso, template, key, tmp_path)

        # Check packer init was called
        mock_run.assert_called_once()
        init_args = mock_run.call_args[0][0]
        assert "packer" in init_args
        assert "init" in init_args

        # Check packer build was called with correct vars
        popen_args = mock_popen.call_args[0][0]
        assert "packer" in popen_args
        assert "build" in popen_args
        assert f"iso_path={iso}" in " ".join(popen_args)
        assert f"ssh_private_key_file={key}" in " ".join(popen_args)


class TestVerifyMachine:
    @patch("autoboot.test.check_test_prerequisites")
    @patch("autoboot.test.load_config")
    @patch("autoboot.test.find_latest_iso")
    @patch("autoboot.test.get_packer_template")
    @patch("autoboot.test.run_vm_test")
    def test_orchestrates_full_flow(  # noqa: PLR0913
        self, mock_run, mock_template, mock_find_iso,
        mock_load, mock_prereq, tmp_path: Path,
    ):
        # Set up project structure
        configs_dir = tmp_path / "configs" / "web-01"
        configs_dir.mkdir(parents=True)
        keys_dir = tmp_path / "keys"
        keys_dir.mkdir()
        (keys_dir / "ansible").write_text("private-key")

        mock_config = MagicMock()
        mock_config.distro = "ubuntu"
        mock_load.return_value = mock_config
        mock_find_iso.return_value = tmp_path / "test.iso"
        mock_template.return_value = tmp_path / "template.pkr.hcl"
        mock_run.return_value = VmTestResult(
            passed=True, output="All checks passed", duration=120.0,
        )

        result = verify_machine("web-01", root=tmp_path)

        assert result.passed is True
        mock_prereq.assert_called_once()
        mock_load.assert_called_once()
        mock_find_iso.assert_called_once()
        mock_template.assert_called_once_with("ubuntu", tmp_path)
        mock_run.assert_called_once()

    @patch("autoboot.test.check_test_prerequisites")
    @patch("autoboot.test.load_config")
    @patch("autoboot.test.find_latest_iso", return_value=None)
    def test_raises_when_no_built_iso(
        self, mock_find_iso, mock_load, mock_prereq, tmp_path: Path,
    ):
        mock_config = MagicMock()
        mock_config.distro = "ubuntu"
        mock_load.return_value = mock_config

        with pytest.raises(FileNotFoundError, match="No built ISO found"):
            verify_machine("web-01", root=tmp_path)

    @patch("autoboot.test.check_test_prerequisites")
    @patch("autoboot.test.load_config")
    @patch("autoboot.test.find_latest_iso")
    def test_raises_when_no_ssh_key(
        self, mock_find_iso, mock_load, mock_prereq, tmp_path: Path,
    ):
        keys_dir = tmp_path / "keys"
        keys_dir.mkdir()
        # No private key file

        mock_config = MagicMock()
        mock_config.distro = "ubuntu"
        mock_load.return_value = mock_config
        mock_find_iso.return_value = tmp_path / "test.iso"

        with pytest.raises(FileNotFoundError, match="SSH private key"):
            verify_machine("web-01", root=tmp_path)

    @patch("autoboot.test.check_test_prerequisites")
    @patch("autoboot.test.load_config")
    @patch("autoboot.test.find_latest_iso")
    @patch("autoboot.test.get_packer_template")
    @patch("autoboot.test.run_vm_test")
    def test_cleans_up_vm_output(  # noqa: PLR0913
        self, mock_run, mock_template, mock_find_iso,
        mock_load, mock_prereq, tmp_path: Path,
    ):
        keys_dir = tmp_path / "keys"
        keys_dir.mkdir()
        (keys_dir / "ansible").write_text("private-key")

        # Create a pre-existing output dir
        output_dir = tmp_path / "tests" / "e2e" / "output" / "ubuntu"
        output_dir.mkdir(parents=True)

        mock_config = MagicMock()
        mock_config.distro = "ubuntu"
        mock_load.return_value = mock_config
        mock_find_iso.return_value = tmp_path / "test.iso"
        mock_template.return_value = tmp_path / "template.pkr.hcl"
        mock_run.return_value = VmTestResult(
            passed=True, output="ok", duration=10.0,
        )

        verify_machine("web-01", root=tmp_path)

        # Output dir should be cleaned up
        assert not output_dir.exists()
