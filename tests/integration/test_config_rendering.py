"""Integration tests: full config round-trip (create → load → render → validate)."""

from pathlib import Path

import yaml

from autoboot.config import create_config, load_config
from autoboot.distros import get_handler
from autoboot.models import AdminConfig

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


class TestUbuntuRoundTrip:
    def test_create_load_render_validate(self, tmp_path: Path):
        config_path = create_config("web-01", distro="ubuntu", configs_dir=tmp_path)
        config = load_config(config_path)

        config.admin = AdminConfig(
            username="admin", password_hash="$6$roundtriphash"
        )

        handler = get_handler("ubuntu")
        ssh_key = "ssh-ed25519 ROUNDTRIPKEY ansible@test"
        rendered = handler.render_config(config, ssh_key, TEMPLATES_DIR)

        errors = handler.validate_rendered_config(rendered)
        assert errors == [], f"Validation errors: {errors}"

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        assert parsed["autoinstall"]["identity"]["hostname"] == "web-01"
        assert "ROUNDTRIPKEY" in rendered["nocloud/user-data"]
        assert "ansible" in rendered["nocloud/user-data"]

    def test_static_ip_round_trip(self, tmp_path: Path):
        config_path = create_config("db-01", distro="ubuntu", configs_dir=tmp_path)
        config = load_config(config_path)

        config.admin.password_hash = "$6$hash"
        config.network.type = "static"
        config.network.address = "10.0.0.50/24"
        config.network.gateway = "10.0.0.1"
        config.network.dns = ["8.8.8.8"]

        handler = get_handler("ubuntu")
        rendered = handler.render_config(config, "ssh-ed25519 KEY", TEMPLATES_DIR)

        parsed = yaml.safe_load(rendered["nocloud/user-data"])
        ethernets = parsed["autoinstall"]["network"]["ethernets"]
        assert ethernets["id0"]["dhcp4"] is False
        assert "10.0.0.50/24" in ethernets["id0"]["addresses"]


class TestDebianRoundTrip:
    def test_create_load_render_validate(self, tmp_path: Path):
        config_path = create_config("mail-01", distro="debian", configs_dir=tmp_path)
        config = load_config(config_path)

        config.admin = AdminConfig(
            username="admin", password_hash="$6$roundtriphash"
        )

        handler = get_handler("debian")
        ssh_key = "ssh-ed25519 ROUNDTRIPKEY ansible@test"
        rendered = handler.render_config(config, ssh_key, TEMPLATES_DIR)

        errors = handler.validate_rendered_config(rendered)
        assert errors == [], f"Validation errors: {errors}"

        preseed = rendered["preseed.cfg"]
        assert "mail-01" in preseed
        assert "ROUNDTRIPKEY" in preseed
        assert "ansible" in preseed
