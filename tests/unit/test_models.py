"""Tests for autoboot.models module."""

from autoboot.models import AdminConfig, MachineConfig, NetworkConfig, StorageConfig


class TestNetworkConfig:
    def test_defaults_to_dhcp(self):
        net = NetworkConfig()
        assert net.type == "dhcp"
        assert net.validate() == []

    def test_static_requires_address_and_gateway(self):
        net = NetworkConfig(type="static")
        errors = net.validate()
        assert "Static network requires 'address'." in errors
        assert "Static network requires 'gateway'." in errors

    def test_valid_static(self):
        net = NetworkConfig(
            type="static",
            address="192.168.1.100/24",
            gateway="192.168.1.1",
            dns=["8.8.8.8"],
        )
        assert net.validate() == []

    def test_invalid_type(self):
        net = NetworkConfig(type="bonded")
        errors = net.validate()
        assert any("Invalid network type" in e for e in errors)


class TestStorageConfig:
    def test_defaults_to_lvm(self):
        storage = StorageConfig()
        assert storage.layout == "lvm"
        assert storage.validate() == []

    def test_direct_layout_valid(self):
        storage = StorageConfig(layout="direct")
        assert storage.validate() == []

    def test_invalid_layout(self):
        storage = StorageConfig(layout="zfs")
        errors = storage.validate()
        assert any("Invalid storage layout" in e for e in errors)


class TestAdminConfig:
    def test_requires_password_hash(self):
        admin = AdminConfig(username="admin", password_hash="")
        errors = admin.validate()
        assert "Admin password_hash is required." in errors

    def test_requires_username(self):
        admin = AdminConfig(username="", password_hash="$6$hash")
        errors = admin.validate()
        assert "Admin username is required." in errors

    def test_valid_admin(self):
        admin = AdminConfig(username="admin", password_hash="$6$hash")
        assert admin.validate() == []


class TestMachineConfig:
    def test_minimal_valid_config(self):
        config = MachineConfig(
            machine_name="test-server",
            distro="ubuntu",
            distro_version="24.04.3",
            admin=AdminConfig(username="admin", password_hash="$6$hash"),
        )
        assert config.validate() == []

    def test_hostname_defaults_to_machine_name(self):
        config = MachineConfig(
            machine_name="test-server",
            distro="ubuntu",
            distro_version="24.04.3",
        )
        assert config.hostname == "test-server"

    def test_custom_hostname(self):
        config = MachineConfig(
            machine_name="test-server",
            distro="ubuntu",
            distro_version="24.04.3",
            hostname="my-custom-host",
        )
        assert config.hostname == "my-custom-host"

    def test_missing_machine_name(self):
        config = MachineConfig(
            machine_name="",
            distro="ubuntu",
            distro_version="24.04.3",
        )
        errors = config.validate()
        assert "machine_name is required." in errors

    def test_missing_distro(self):
        config = MachineConfig(
            machine_name="test",
            distro="",
            distro_version="24.04.3",
        )
        errors = config.validate()
        assert "distro is required." in errors

    def test_missing_distro_version(self):
        config = MachineConfig(
            machine_name="test",
            distro="ubuntu",
            distro_version="",
        )
        errors = config.validate()
        assert "distro_version is required." in errors

    def test_default_values(self):
        config = MachineConfig(
            machine_name="test",
            distro="ubuntu",
            distro_version="24.04.3",
        )
        assert config.locale == "en_US.UTF-8"
        assert config.keyboard_layout == "us"
        assert config.timezone == "UTC"
        assert config.packages == []
        assert config.extra_late_commands == []

    def test_validates_nested_configs(self):
        config = MachineConfig(
            machine_name="test",
            distro="ubuntu",
            distro_version="24.04.3",
            network=NetworkConfig(type="invalid"),
            storage=StorageConfig(layout="invalid"),
        )
        errors = config.validate()
        assert any("network type" in e.lower() for e in errors)
        assert any("storage layout" in e.lower() for e in errors)
