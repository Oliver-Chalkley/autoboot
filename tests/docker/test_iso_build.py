"""Docker integration tests — build ISOs with fake source, verify contents.

Inspired by create_on_premise_server_automated_installer integration tests.
Each distro's ISO is built once (module-scoped fixture), then individual
tests inspect the extracted contents.

Run with: uv run pytest -m docker
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.docker

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class TestUbuntuIsoBuild:
    """Verify Ubuntu ISO build injects configs correctly."""

    def test_iso_was_produced(self, ubuntu_iso_contents: Path):
        built = ubuntu_iso_contents.parent / "built.iso"
        assert built.exists()
        assert built.stat().st_size > 0

    def test_user_data_injected(self, ubuntu_iso_contents: Path):
        assert (ubuntu_iso_contents / "nocloud" / "user-data").exists()

    def test_meta_data_injected(self, ubuntu_iso_contents: Path):
        assert (ubuntu_iso_contents / "nocloud" / "meta-data").exists()

    def test_user_data_contains_autoinstall(self, ubuntu_iso_contents: Path):
        user_data = (ubuntu_iso_contents / "nocloud" / "user-data").read_text()
        assert "autoinstall" in user_data

    def test_user_data_contains_ansible_user(self, ubuntu_iso_contents: Path):
        user_data = (ubuntu_iso_contents / "nocloud" / "user-data").read_text()
        assert "name: ansible" in user_data

    def test_ssh_key_present_in_user_data(self, ubuntu_iso_contents: Path):
        user_data = (ubuntu_iso_contents / "nocloud" / "user-data").read_text()
        test_key = (FIXTURES_DIR / "keys" / "ansible.pub").read_text().strip()
        assert test_key in user_data

    def test_hostname_in_user_data(self, ubuntu_iso_contents: Path):
        user_data = (ubuntu_iso_contents / "nocloud" / "user-data").read_text()
        assert "hostname: test-ubuntu" in user_data

    def test_sudoers_late_command(self, ubuntu_iso_contents: Path):
        user_data = (ubuntu_iso_contents / "nocloud" / "user-data").read_text()
        assert "sudoers.d/ansible" in user_data

    def test_autoinstall_success_marker(self, ubuntu_iso_contents: Path):
        user_data = (ubuntu_iso_contents / "nocloud" / "user-data").read_text()
        assert "autoinstall-success" in user_data

    def test_grub_has_autoinstall_param(self, ubuntu_iso_contents: Path):
        grub_cfg = (ubuntu_iso_contents / "boot" / "grub" / "grub.cfg").read_text()
        assert "autoinstall" in grub_cfg

    def test_grub_has_nocloud_datasource(self, ubuntu_iso_contents: Path):
        grub_cfg = (ubuntu_iso_contents / "boot" / "grub" / "grub.cfg").read_text()
        assert "ds=nocloud" in grub_cfg


class TestDebianIsoBuild:
    """Verify Debian ISO build injects preseed correctly."""

    def test_iso_was_produced(self, debian_iso_contents: Path):
        built = debian_iso_contents.parent / "built.iso"
        assert built.exists()
        assert built.stat().st_size > 0

    def test_preseed_injected(self, debian_iso_contents: Path):
        assert (debian_iso_contents / "preseed.cfg").exists()

    def test_preseed_has_debconf_directives(self, debian_iso_contents: Path):
        preseed = (debian_iso_contents / "preseed.cfg").read_text()
        assert "d-i" in preseed

    def test_preseed_configures_user(self, debian_iso_contents: Path):
        preseed = (debian_iso_contents / "preseed.cfg").read_text()
        assert "passwd/username" in preseed or "passwd/user-fullname" in preseed

    def test_ssh_key_present_in_preseed(self, debian_iso_contents: Path):
        preseed = (debian_iso_contents / "preseed.cfg").read_text()
        test_key = (FIXTURES_DIR / "keys" / "ansible.pub").read_text().strip()
        assert test_key in preseed

    def test_hostname_in_preseed(self, debian_iso_contents: Path):
        preseed = (debian_iso_contents / "preseed.cfg").read_text()
        assert "test-debian" in preseed

    def test_grub_has_preseed_params(self, debian_iso_contents: Path):
        grub_cfg = (debian_iso_contents / "boot" / "grub" / "grub.cfg").read_text()
        assert "preseed" in grub_cfg or "auto=true" in grub_cfg
