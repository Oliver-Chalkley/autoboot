"""Machine config CRUD and validation."""

from pathlib import Path

import yaml

from autoboot.distros import get_handler
from autoboot.models import AdminConfig, MachineConfig, NetworkConfig, StorageConfig
from autoboot.paths import get_configs_dir as _get_configs_dir


def load_config(config_path: Path) -> MachineConfig:
    """Load a machine config from a YAML file."""
    if not config_path.exists():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        msg = f"Config file must contain a YAML mapping: {config_path}"
        raise ValueError(msg)

    network_data = raw.get("network", {})
    network = NetworkConfig(
        type=network_data.get("type", "dhcp"),
        interface=network_data.get("interface", "en*"),
        address=network_data.get("address", ""),
        gateway=network_data.get("gateway", ""),
        dns=network_data.get("dns", []),
    )

    storage_data = raw.get("storage", {})
    storage = StorageConfig(
        layout=storage_data.get("layout", "lvm"),
        match=storage_data.get("match", "largest"),
    )

    admin_data = raw.get("admin", {})
    admin = AdminConfig(
        username=admin_data.get("username", "admin"),
        password_hash=admin_data.get("password_hash", ""),
        real_name=admin_data.get("real_name", "Administrator"),
    )

    return MachineConfig(
        machine_name=raw.get("machine_name", ""),
        distro=raw.get("distro", ""),
        distro_version=raw.get("distro_version", ""),
        hostname=raw.get("hostname", ""),
        locale=raw.get("locale", "en_US.UTF-8"),
        keyboard_layout=raw.get("keyboard_layout", "us"),
        timezone=raw.get("timezone", "UTC"),
        network=network,
        storage=storage,
        admin=admin,
        packages=raw.get("packages", []),
        extra_late_commands=raw.get("extra_late_commands", []),
    )


def save_config(config: MachineConfig, config_path: Path) -> None:
    """Save a machine config to a YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "machine_name": config.machine_name,
        "distro": config.distro,
        "distro_version": config.distro_version,
        "hostname": config.hostname,
        "locale": config.locale,
        "keyboard_layout": config.keyboard_layout,
        "timezone": config.timezone,
        "network": {
            "type": config.network.type,
            "interface": config.network.interface,
            "address": config.network.address,
            "gateway": config.network.gateway,
            "dns": config.network.dns,
        },
        "storage": {
            "layout": config.storage.layout,
            "match": config.storage.match,
        },
        "admin": {
            "username": config.admin.username,
            "password_hash": config.admin.password_hash,
            "real_name": config.admin.real_name,
        },
        "packages": config.packages,
        "extra_late_commands": config.extra_late_commands,
    }

    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def create_config(
    machine_name: str,
    distro: str = "ubuntu",
    distro_version: str = "",
    configs_dir: Path | None = None,
) -> Path:
    """Create a new machine config with defaults. Returns path to config file."""
    configs_dir = configs_dir or _get_configs_dir()

    if not distro_version:
        handler = get_handler(distro)
        distro_version = handler.supported_versions[-1]

    config = MachineConfig(
        machine_name=machine_name,
        distro=distro,
        distro_version=distro_version,
        admin=AdminConfig(
            username="admin",
            password_hash="CHANGE_ME",
        ),
    )

    config_path = configs_dir / machine_name / "config.yaml"
    save_config(config, config_path)
    return config_path


def list_configs(configs_dir: Path) -> list[MachineConfig]:
    """Find and load all machine configs."""
    configs = []
    if not configs_dir.exists():
        return configs

    for config_file in sorted(configs_dir.glob("*/config.yaml")):
        try:
            configs.append(load_config(config_file))
        except (ValueError, yaml.YAMLError):
            continue

    return configs


def validate_config(config: MachineConfig) -> list[str]:
    """Validate a machine config. Returns list of errors."""
    errors = config.validate()

    try:
        get_handler(config.distro)
    except ValueError as e:
        errors.append(str(e))

    return errors
