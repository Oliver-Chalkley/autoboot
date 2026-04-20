"""Fedora kickstart distro handler."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from autoboot.models import MachineConfig

_ARCH_MAP = {"amd64": "x86_64"}

# Fedora release compose suffixes (version -> compose ID).
# Each new Fedora release needs its suffix added here.
_COMPOSE_SUFFIX: dict[str, str] = {
    "42": "1.1",
    "43": "1.6",
}


class FedoraHandler:
    """Handler for Fedora kickstart-based installations."""

    @property
    def name(self) -> str:
        return "fedora"

    @property
    def supported_versions(self) -> list[str]:
        return sorted(_COMPOSE_SUFFIX.keys())

    def _fedora_arch(self, arch: str) -> str:
        return _ARCH_MAP.get(arch, arch)

    def iso_url(self, version: str, arch: str = "amd64") -> str:
        fa = self._fedora_arch(arch)
        suffix = _COMPOSE_SUFFIX.get(version, "1.1")
        return (
            f"https://download.fedoraproject.org/pub/fedora/linux/releases"
            f"/{version}/Server/{fa}/iso/"
            f"Fedora-Server-dvd-{fa}-{version}-{suffix}.iso"
        )

    def checksum_url(self, version: str, arch: str = "amd64") -> str:
        fa = self._fedora_arch(arch)
        suffix = _COMPOSE_SUFFIX.get(version, "1.1")
        return (
            f"https://download.fedoraproject.org/pub/fedora/linux/releases"
            f"/{version}/Server/{fa}/iso/"
            f"Fedora-Server-{version}-{suffix}-{fa}-CHECKSUM"
        )

    def iso_filename(self, version: str, arch: str = "amd64") -> str:
        fa = self._fedora_arch(arch)
        suffix = _COMPOSE_SUFFIX.get(version, "1.1")
        return f"Fedora-Server-dvd-{fa}-{version}-{suffix}.iso"

    def render_config(
        self, config: MachineConfig, ssh_key: str, templates_dir: Path
    ) -> dict[str, str]:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir / "fedora")),
            keep_trailing_newline=True,
        )

        kickstart_template = env.get_template("kickstart.ks.j2")
        kickstart = kickstart_template.render(
            config=config,
            ssh_key=ssh_key,
        )

        return {
            "kickstart.ks": kickstart,
        }

    def grub_sed_pattern(self) -> str:
        return r"s|quiet|inst.ks=cdrom:/kickstart.ks quiet|"

    def validate_rendered_config(self, rendered: dict[str, str]) -> list[str]:
        errors = []
        if "kickstart.ks" not in rendered:
            errors.append("Missing kickstart.ks in rendered config.")
            return errors

        kickstart = rendered["kickstart.ks"]
        if "%packages" not in kickstart and "lang " not in kickstart:
            errors.append("kickstart.ks does not contain kickstart directives.")
        if "user " not in kickstart and "useradd" not in kickstart:
            errors.append("kickstart.ks does not configure a user.")

        return errors
