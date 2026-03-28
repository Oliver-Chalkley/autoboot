"""Tests for Debian distro handler."""

from pathlib import Path

from autoboot.distros.base import DistroHandler
from autoboot.distros.debian import DebianHandler
from autoboot.models import AdminConfig, MachineConfig, NetworkConfig


def make_config(**overrides) -> MachineConfig:
    defaults = {
        "machine_name": "test-server",
        "distro": "debian",
        "distro_version": "12.9",
        "admin": AdminConfig(username="admin", password_hash="$6$testhash"),
    }
    defaults.update(overrides)
    return MachineConfig(**defaults)


class TestDebianHandler:
    def setup_method(self):
        self.handler = DebianHandler()
        self.templates_dir = Path(__file__).resolve().parents[3] / "templates"

    def test_implements_protocol(self):
        assert isinstance(self.handler, DistroHandler)

    def test_name(self):
        assert self.handler.name == "debian"

    def test_supported_versions(self):
        versions = self.handler.supported_versions
        assert "12.9" in versions

    def test_iso_url(self):
        url = self.handler.iso_url("12.9")
        assert url == (
            "https://cdimage.debian.org/debian-cd/12.9/amd64/iso-cd/"
            "debian-12.9-amd64-netinst.iso"
        )

    def test_iso_url_custom_arch(self):
        url = self.handler.iso_url("12.9", arch="arm64")
        assert "arm64" in url

    def test_checksum_url(self):
        url = self.handler.checksum_url("12.9")
        assert "SHA256SUMS" in url
        assert "12.9" in url

    def test_iso_filename(self):
        name = self.handler.iso_filename("12.9")
        assert name == "debian-12.9-amd64-netinst.iso"

    def test_grub_sed_pattern(self):
        pattern = self.handler.grub_sed_pattern()
        assert "auto=true" in pattern
        assert "preseed" in pattern

    def test_render_config_produces_preseed(self):
        config = make_config()
        ssh_key = "ssh-ed25519 AAAA... ansible@server"
        rendered = self.handler.render_config(config, ssh_key, self.templates_dir)

        assert "preseed.cfg" in rendered
        preseed = rendered["preseed.cfg"]
        assert "d-i" in preseed

    def test_render_config_contains_ssh_key(self):
        config = make_config()
        ssh_key = "ssh-ed25519 TESTKEY123 ansible@server"
        rendered = self.handler.render_config(config, ssh_key, self.templates_dir)

        assert "TESTKEY123" in rendered["preseed.cfg"]

    def test_render_config_contains_hostname(self):
        config = make_config(hostname="my-debian-host")
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        assert "my-debian-host" in rendered["preseed.cfg"]

    def test_render_config_contains_ansible_user(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        preseed = rendered["preseed.cfg"]
        assert "ansible" in preseed
        assert "NOPASSWD:ALL" in preseed

    def test_render_config_contains_packages(self):
        config = make_config(packages=["vim", "htop"])
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        preseed = rendered["preseed.cfg"]
        assert "vim" in preseed
        assert "htop" in preseed
        assert "python3" in preseed

    def test_render_config_dhcp(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        preseed = rendered["preseed.cfg"]
        assert "disable_autoconfig boolean false" in preseed

    def test_render_config_static_ip(self):
        config = make_config(
            network=NetworkConfig(
                type="static",
                address="192.168.1.100/24",
                gateway="192.168.1.1",
                dns=["8.8.8.8"],
            )
        )
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        preseed = rendered["preseed.cfg"]
        assert "disable_autoconfig boolean true" in preseed
        assert "192.168.1.100" in preseed

    def test_validate_rendered_config_valid(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )
        errors = self.handler.validate_rendered_config(rendered)
        assert errors == []

    def test_validate_rendered_config_missing_preseed(self):
        errors = self.handler.validate_rendered_config({})
        assert any("Missing" in e for e in errors)

    def test_validate_rendered_config_no_directives(self):
        errors = self.handler.validate_rendered_config({"preseed.cfg": "nothing here"})
        assert any("d-i" in e for e in errors)
