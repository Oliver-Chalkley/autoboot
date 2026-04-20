"""Tests for Fedora distro handler."""

from pathlib import Path

from autoboot.distros.base import DistroHandler
from autoboot.distros.fedora import FedoraHandler
from autoboot.models import AdminConfig, MachineConfig, NetworkConfig


def make_config(**overrides) -> MachineConfig:
    defaults = {
        "machine_name": "test-server",
        "distro": "fedora",
        "distro_version": "43",
        "admin": AdminConfig(username="admin", password_hash="$6$testhash"),
    }
    defaults.update(overrides)
    return MachineConfig(**defaults)


class TestFedoraHandler:
    def setup_method(self):
        self.handler = FedoraHandler()
        self.templates_dir = Path(__file__).resolve().parents[3] / "templates"

    def test_implements_protocol(self):
        assert isinstance(self.handler, DistroHandler)

    def test_name(self):
        assert self.handler.name == "fedora"

    def test_supported_versions(self):
        versions = self.handler.supported_versions
        assert "42" in versions
        assert "43" in versions

    def test_iso_url(self):
        url = self.handler.iso_url("43")
        assert url == (
            "https://download.fedoraproject.org/pub/fedora/linux/releases"
            "/43/Server/x86_64/iso/Fedora-Server-dvd-x86_64-43-1.6.iso"
        )

    def test_iso_url_translates_amd64_to_x86_64(self):
        url = self.handler.iso_url("43", arch="amd64")
        assert "x86_64" in url
        assert "amd64" not in url

    def test_iso_url_custom_arch(self):
        url = self.handler.iso_url("43", arch="aarch64")
        assert "aarch64" in url

    def test_checksum_url(self):
        url = self.handler.checksum_url("43")
        assert "CHECKSUM" in url
        assert "43" in url

    def test_iso_filename(self):
        name = self.handler.iso_filename("43")
        assert name == "Fedora-Server-dvd-x86_64-43-1.6.iso"

    def test_grub_sed_pattern(self):
        pattern = self.handler.grub_sed_pattern()
        assert "inst.ks" in pattern
        assert "kickstart.ks" in pattern

    def test_render_config_produces_kickstart(self):
        config = make_config()
        ssh_key = "ssh-ed25519 AAAA... ansible@server"
        rendered = self.handler.render_config(config, ssh_key, self.templates_dir)

        assert "kickstart.ks" in rendered
        kickstart = rendered["kickstart.ks"]
        assert "lang" in kickstart

    def test_render_config_contains_ssh_key(self):
        config = make_config()
        ssh_key = "ssh-ed25519 TESTKEY123 ansible@server"
        rendered = self.handler.render_config(config, ssh_key, self.templates_dir)

        assert "TESTKEY123" in rendered["kickstart.ks"]

    def test_render_config_contains_hostname(self):
        config = make_config(hostname="my-fedora-host")
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        assert "my-fedora-host" in rendered["kickstart.ks"]

    def test_render_config_contains_ansible_user(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        kickstart = rendered["kickstart.ks"]
        assert "ansible" in kickstart
        assert "NOPASSWD:ALL" in kickstart

    def test_render_config_contains_packages(self):
        config = make_config(packages=["vim", "htop"])
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        kickstart = rendered["kickstart.ks"]
        assert "vim" in kickstart
        assert "htop" in kickstart
        assert "python3" in kickstart

    def test_render_config_dhcp(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        kickstart = rendered["kickstart.ks"]
        assert "--bootproto=dhcp" in kickstart

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

        kickstart = rendered["kickstart.ks"]
        assert "--bootproto=static" in kickstart
        assert "192.168.1.100" in kickstart

    def test_validate_rendered_config_valid(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )
        errors = self.handler.validate_rendered_config(rendered)
        assert errors == []

    def test_validate_rendered_config_missing_kickstart(self):
        errors = self.handler.validate_rendered_config({})
        assert any("Missing" in e for e in errors)

    def test_validate_rendered_config_no_directives(self):
        errors = self.handler.validate_rendered_config({"kickstart.ks": "nothing here"})
        assert len(errors) > 0
