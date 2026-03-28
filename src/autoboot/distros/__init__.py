"""Distro handler registry."""

from autoboot.distros.base import DistroHandler
from autoboot.distros.debian import DebianHandler
from autoboot.distros.ubuntu import UbuntuHandler

_HANDLERS: dict[str, type[DistroHandler]] = {
    "ubuntu": UbuntuHandler,
    "debian": DebianHandler,
}


def get_handler(distro_name: str) -> DistroHandler:
    """Get a handler instance by distro name."""
    if distro_name not in _HANDLERS:
        available = ", ".join(sorted(_HANDLERS.keys()))
        msg = f"Unknown distro '{distro_name}'. Available: {available}"
        raise ValueError(msg)
    return _HANDLERS[distro_name]()


def list_distros() -> list[str]:
    """Return names of all registered distros."""
    return sorted(_HANDLERS.keys())
