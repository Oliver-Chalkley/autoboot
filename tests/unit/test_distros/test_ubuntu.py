"""Tests for Ubuntu distro handler."""

from pathlib import Path

import yaml

from autoboot.distros.base import DistroHandler
from autoboot.distros.ubuntu import UbuntuHandler
from autoboot.models import AdminConfig, MachineConfig, NetworkConfig


def make_config(**overrides) -> MachineConfig:
    defaults = {
        "machine_name": "test-server",
        "distro": "ubuntu",
        "distro_version": "24.04.3",
        "admin": AdminConfig(username="admin", password_hash="$6$testhash"),
    }
    defaults.update(overrides)
    return MachineConfig(**defaults)


class TestUbuntuHandler:
    def setup_method(self):
        self.handler = UbuntuHandler()
        self.templates_dir = Path(__file__).resolve().parents[3] / "templates"

    def test_implements_protocol(self):
        assert isinstance(self.handler, DistroHandler)

    def test_name(self):
        assert self.handler.name == "ubuntu"

    def test_supported_versions(self):
        versions = self.handler.supported_versions
        assert "24.04" in versions
        assert "24.04.3" in versions

    def test_iso_url(self):
        url = self.handler.iso_url("24.04.3")
        assert url == (
            "https://releases.ubuntu.com/24.04.3/"
            "ubuntu-24.04.3-live-server-amd64.iso"
        )

    def test_iso_url_custom_arch(self):
        url = self.handler.iso_url("24.04.3", arch="arm64")
        assert "arm64" in url

    def test_checksum_url(self):
        url = self.handler.checksum_url("24.04.3")
        assert url == "https://releases.ubuntu.com/24.04.3/SHA256SUMS"

    def test_iso_filename(self):
        name = self.handler.iso_filename("24.04.3")
        assert name == "ubuntu-24.04.3-live-server-amd64.iso"

    def test_grub_sed_pattern(self):
        pattern = self.handler.grub_sed_pattern()
        assert "autoinstall" in pattern
        assert "nocloud" in pattern

    def test_render_config_produces_valid_yaml(self):
        config = make_config()
        ssh_key = "ssh-ed25519 AAAA... ansible@server"
        rendered = self.handler.render_config(config, ssh_key, self.templates_dir)

        assert "nocloud/user-data" in rendered
        assert "nocloud/meta-data" in rendered

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        assert "autoinstall" in parsed

    def test_render_config_contains_ssh_key(self):
        config = make_config()
        ssh_key = "ssh-ed25519 TESTKEY123 ansible@server"
        rendered = self.handler.render_config(config, ssh_key, self.templates_dir)

        assert "TESTKEY123" in rendered["nocloud/user-data"]

    def test_render_config_contains_hostname(self):
        config = make_config(hostname="my-custom-host")
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        assert parsed["autoinstall"]["identity"]["hostname"] == "my-custom-host"

    def test_render_config_contains_ansible_user(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        user_data = rendered["nocloud/user-data"]
        assert "ansible" in user_data
        assert "NOPASSWD:ALL" in user_data

    def test_render_config_contains_packages(self):
        config = make_config(packages=["vim", "htop"])
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        packages = parsed["autoinstall"]["packages"]
        assert "vim" in packages
        assert "htop" in packages
        assert "python3" in packages

    def test_render_config_dhcp(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        ethernets = parsed["autoinstall"]["network"]["ethernets"]
        assert ethernets["id0"]["dhcp4"] is True

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

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        ethernets = parsed["autoinstall"]["network"]["ethernets"]
        assert ethernets["id0"]["dhcp4"] is False
        assert "192.168.1.100/24" in ethernets["id0"]["addresses"]

    def test_render_meta_data(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )

        meta = rendered["nocloud/meta-data"]
        assert "test-server" in meta

    def test_validate_rendered_config_valid(self):
        config = make_config()
        rendered = self.handler.render_config(
            config, "ssh-ed25519 KEY", self.templates_dir
        )
        errors = self.handler.validate_rendered_config(rendered)
        assert errors == []

    def test_validate_rendered_config_missing_user_data(self):
        errors = self.handler.validate_rendered_config({})
        assert any("Missing" in e for e in errors)

    def test_validate_rendered_config_invalid_yaml(self):
        errors = self.handler.validate_rendered_config(
            {"nocloud/user-data": "{{invalid yaml"}
        )
        assert any("not valid YAML" in e for e in errors)

    def test_validate_rendered_config_missing_autoinstall(self):
        errors = self.handler.validate_rendered_config(
            {"nocloud/user-data": "foo: bar"}
        )
        assert any("autoinstall" in e for e in errors)
