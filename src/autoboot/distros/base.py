"""Base protocol for distro handlers."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from autoboot.models import MachineConfig


@runtime_checkable
class DistroHandler(Protocol):
    """Protocol that all distro handlers must implement."""

    @property
    def name(self) -> str: ...

    @property
    def supported_versions(self) -> list[str]: ...

    def iso_url(self, version: str, arch: str = "amd64") -> str:
        """Return the official download URL for this distro's ISO."""
        ...

    def checksum_url(self, version: str, arch: str = "amd64") -> str:
        """Return the URL for the SHA256SUMS file."""
        ...

    def iso_filename(self, version: str, arch: str = "amd64") -> str:
        """Return the expected ISO filename."""
        ...

    def render_config(
        self, config: MachineConfig, ssh_key: str, templates_dir: Path
    ) -> dict[str, str]:
        """Render distro-specific installer config files.

        Returns a dict mapping relative file paths (inside the ISO)
        to their rendered content.
        """
        ...

    def grub_sed_pattern(self) -> str:
        """Return the sed substitution pattern to modify GRUB for automated install."""
        ...

    def validate_rendered_config(self, rendered: dict[str, str]) -> list[str]:
        """Validate the rendered config. Returns list of error messages."""
        ...
