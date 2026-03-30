"""VM E2E tests — boot real Ubuntu ISO in QEMU, validate installation.

These tests download a real Ubuntu 24.04.3 ISO, build a customized ISO
with autoboot, then boot it in a QEMU VM via Packer. Packer's provisioners
validate the install (ansible user, SSH key, sudo, packages, etc.).

Prerequisites: packer, qemu-system-x86_64, xorriso, curl, ~3GB disk space.
Runtime: ~20-30 minutes.

Run with: uv run pytest -m vm
"""

import subprocess

import pytest

PackerResult = subprocess.CompletedProcess

pytestmark = pytest.mark.vm


class TestUbuntuVmInstall:
    """Full end-to-end: build ISO, boot VM, validate installation."""

    def test_packer_build_succeeds(
        self, packer_ubuntu_result: PackerResult,
    ):
        """Packer boots ISO, connects via SSH, runs validations."""
        assert packer_ubuntu_result.returncode == 0, (
            f"Packer build failed:\n"
            f"STDOUT:\n{packer_ubuntu_result.stdout}\n"
            f"STDERR:\n{packer_ubuntu_result.stderr}"
        )

    def test_ansible_user_validated(
        self, packer_ubuntu_result: PackerResult,
    ):
        """Shell provisioner checks the ansible user exists."""
        if packer_ubuntu_result.returncode != 0:
            pytest.skip("Packer build failed")
        assert "Checking ansible user" in packer_ubuntu_result.stdout

    def test_sudo_validated(
        self, packer_ubuntu_result: PackerResult,
    ):
        """Shell provisioner checks passwordless sudo."""
        if packer_ubuntu_result.returncode != 0:
            pytest.skip("Packer build failed")
        assert "Checking passwordless sudo" in packer_ubuntu_result.stdout

    def test_ssh_key_validated(
        self, packer_ubuntu_result: PackerResult,
    ):
        """Shell provisioner checks SSH authorized_keys."""
        if packer_ubuntu_result.returncode != 0:
            pytest.skip("Packer build failed")
        assert "Checking SSH authorized_keys" in packer_ubuntu_result.stdout

    def test_packages_validated(
        self, packer_ubuntu_result: PackerResult,
    ):
        """Shell provisioner checks python3 and openssh-server."""
        if packer_ubuntu_result.returncode != 0:
            pytest.skip("Packer build failed")
        assert "Checking packages" in packer_ubuntu_result.stdout

    def test_autoinstall_marker_validated(
        self, packer_ubuntu_result: PackerResult,
    ):
        """Shell provisioner checks the autoinstall success marker."""
        if packer_ubuntu_result.returncode != 0:
            pytest.skip("Packer build failed")
        assert "Checking autoinstall marker" in packer_ubuntu_result.stdout

    def test_all_checks_passed(
        self, packer_ubuntu_result: PackerResult,
    ):
        """All Packer inline shell checks should pass."""
        if packer_ubuntu_result.returncode != 0:
            pytest.skip("Packer build failed")
        assert "All checks passed" in packer_ubuntu_result.stdout
