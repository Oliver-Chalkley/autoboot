"""Data models for machine configurations."""

from dataclasses import dataclass, field


@dataclass
class NetworkConfig:
    """Network configuration for a machine."""

    type: str = "dhcp"
    interface: str = "en*"
    address: str = ""
    gateway: str = ""
    dns: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = []
        if self.type not in ("dhcp", "static"):
            errors.append(f"Invalid network type: {self.type!r}. Must be 'dhcp' or 'static'.")
        if self.type == "static":
            if not self.address:
                errors.append("Static network requires 'address'.")
            if not self.gateway:
                errors.append("Static network requires 'gateway'.")
        return errors


@dataclass
class StorageConfig:
    """Storage configuration for a machine."""

    layout: str = "lvm"
    match: str = "largest"

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = []
        if self.layout not in ("lvm", "direct"):
            errors.append(f"Invalid storage layout: {self.layout!r}. Must be 'lvm' or 'direct'.")
        return errors


@dataclass
class AdminConfig:
    """Admin user configuration."""

    username: str = "admin"
    password_hash: str = ""
    real_name: str = "Administrator"

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = []
        if not self.username:
            errors.append("Admin username is required.")
        if not self.password_hash:
            errors.append("Admin password_hash is required.")
        return errors


@dataclass
class MachineConfig:
    """Complete machine configuration."""

    machine_name: str
    distro: str
    distro_version: str
    hostname: str = ""
    locale: str = "en_US.UTF-8"
    keyboard_layout: str = "us"
    timezone: str = "UTC"
    network: NetworkConfig = field(default_factory=NetworkConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    packages: list[str] = field(default_factory=list)
    extra_late_commands: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.hostname:
            self.hostname = self.machine_name

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty list means valid."""
        errors = []
        if not self.machine_name:
            errors.append("machine_name is required.")
        if not self.distro:
            errors.append("distro is required.")
        if not self.distro_version:
            errors.append("distro_version is required.")
        errors.extend(self.network.validate())
        errors.extend(self.storage.validate())
        errors.extend(self.admin.validate())
        return errors
