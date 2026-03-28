"""Tests for autoboot.config module."""

from pathlib import Path

import pytest
import yaml

from autoboot.config import (
    create_config,
    list_configs,
    load_config,
    save_config,
    validate_config,
)
from autoboot.models import AdminConfig, MachineConfig


def make_config_yaml(**overrides) -> dict:
    defaults = {
        "machine_name": "test-server",
        "distro": "ubuntu",
        "distro_version": "24.04.3",
        "hostname": "test-server",
        "admin": {
            "username": "admin",
            "password_hash": "$6$testhash",
        },
    }
    defaults.update(overrides)
    return defaults


class TestLoadConfig:
    def test_load_valid_config(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(make_config_yaml()))

        config = load_config(config_file)
        assert config.machine_name == "test-server"
        assert config.distro == "ubuntu"
        assert config.distro_version == "24.04.3"

    def test_load_config_with_network(self, tmp_path: Path):
        data = make_config_yaml(
            network={"type": "static", "address": "10.0.0.1/24", "gateway": "10.0.0.1"}
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(data))

        config = load_config(config_file)
        assert config.network.type == "static"
        assert config.network.address == "10.0.0.1/24"

    def test_load_config_defaults(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(make_config_yaml()))

        config = load_config(config_file)
        assert config.locale == "en_US.UTF-8"
        assert config.keyboard_layout == "us"
        assert config.network.type == "dhcp"
        assert config.storage.layout == "lvm"

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml_raises(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("just a string")

        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(config_file)


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path: Path):
        config = MachineConfig(
            machine_name="test",
            distro="ubuntu",
            distro_version="24.04.3",
            admin=AdminConfig(username="admin", password_hash="$6$hash"),
        )
        config_path = tmp_path / "machine" / "config.yaml"
        save_config(config, config_path)

        assert config_path.exists()
        loaded = load_config(config_path)
        assert loaded.machine_name == "test"
        assert loaded.distro == "ubuntu"
        assert loaded.admin.password_hash == "$6$hash"

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        config = MachineConfig(
            machine_name="test",
            distro="debian",
            distro_version="12.9",
        )
        config_path = tmp_path / "deep" / "nested" / "config.yaml"
        save_config(config, config_path)

        assert config_path.exists()


class TestCreateConfig:
    def test_create_config_ubuntu(self, tmp_path: Path):
        path = create_config("my-server", distro="ubuntu", configs_dir=tmp_path)

        assert path.exists()
        assert path == tmp_path / "my-server" / "config.yaml"

        config = load_config(path)
        assert config.machine_name == "my-server"
        assert config.distro == "ubuntu"

    def test_create_config_debian(self, tmp_path: Path):
        path = create_config("my-server", distro="debian", configs_dir=tmp_path)

        config = load_config(path)
        assert config.distro == "debian"

    def test_create_config_uses_latest_version(self, tmp_path: Path):
        path = create_config("my-server", distro="ubuntu", configs_dir=tmp_path)

        config = load_config(path)
        assert config.distro_version != ""

    def test_create_config_custom_version(self, tmp_path: Path):
        path = create_config(
            "my-server",
            distro="ubuntu",
            distro_version="24.04",
            configs_dir=tmp_path,
        )

        config = load_config(path)
        assert config.distro_version == "24.04"


class TestListConfigs:
    def test_list_empty_dir(self, tmp_path: Path):
        configs = list_configs(tmp_path)
        assert configs == []

    def test_list_nonexistent_dir(self, tmp_path: Path):
        configs = list_configs(tmp_path / "nonexistent")
        assert configs == []

    def test_list_multiple_configs(self, tmp_path: Path):
        create_config("server-a", distro="ubuntu", configs_dir=tmp_path)
        create_config("server-b", distro="debian", configs_dir=tmp_path)

        configs = list_configs(tmp_path)
        names = [c.machine_name for c in configs]
        assert "server-a" in names
        assert "server-b" in names

    def test_list_skips_invalid_configs(self, tmp_path: Path):
        create_config("valid", distro="ubuntu", configs_dir=tmp_path)
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "config.yaml").write_text("not a mapping")

        configs = list_configs(tmp_path)
        assert len(configs) == 1
        assert configs[0].machine_name == "valid"


class TestValidateConfig:
    def test_valid_config(self):
        config = MachineConfig(
            machine_name="test",
            distro="ubuntu",
            distro_version="24.04.3",
            admin=AdminConfig(username="admin", password_hash="$6$hash"),
        )
        errors = validate_config(config)
        assert errors == []

    def test_unknown_distro(self):
        config = MachineConfig(
            machine_name="test",
            distro="arch",
            distro_version="2024.01",
            admin=AdminConfig(username="admin", password_hash="$6$hash"),
        )
        errors = validate_config(config)
        assert any("Unknown distro" in e for e in errors)

    def test_missing_fields(self):
        config = MachineConfig(
            machine_name="",
            distro="",
            distro_version="",
        )
        errors = validate_config(config)
        assert len(errors) > 0
