"""Debian preseed distro handler."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from autoboot.models import MachineConfig


class DebianHandler:
    """Handler for Debian preseed-based installations."""

    @property
    def name(self) -> str:
        return "debian"

    @property
    def supported_versions(self) -> list[str]:
        return ["12.8", "12.9", "12.10"]

    def iso_url(self, version: str, arch: str = "amd64") -> str:
        return (
            f"https://cdimage.debian.org/debian-cd/{version}/{arch}/iso-cd/"
            f"debian-{version}-{arch}-netinst.iso"
        )

    def checksum_url(self, version: str, arch: str = "amd64") -> str:
        return (
            f"https://cdimage.debian.org/debian-cd/{version}/{arch}/iso-cd/SHA256SUMS"
        )

    def iso_filename(self, version: str, arch: str = "amd64") -> str:
        return f"debian-{version}-{arch}-netinst.iso"

    def render_config(
        self, config: MachineConfig, ssh_key: str, templates_dir: Path
    ) -> dict[str, str]:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir / "debian")),
            keep_trailing_newline=True,
        )

        preseed_template = env.get_template("preseed.cfg.j2")
        preseed = preseed_template.render(
            config=config,
            ssh_key=ssh_key,
        )

        return {
            "preseed.cfg": preseed,
        }

    def grub_sed_pattern(self) -> str:
        return (
            r"s|linux\s\+/install|"
            r"linux /install auto=true priority=critical "
            r"preseed/file=/cdrom/preseed.cfg|g"
        )

    def validate_rendered_config(self, rendered: dict[str, str]) -> list[str]:
        errors = []
        if "preseed.cfg" not in rendered:
            errors.append("Missing preseed.cfg in rendered config.")
            return errors

        preseed = rendered["preseed.cfg"]
        if "d-i" not in preseed:
            errors.append("preseed.cfg does not contain any d-i directives.")
        if "passwd/username" not in preseed and "passwd/user-fullname" not in preseed:
            errors.append("preseed.cfg does not configure a user.")

        return errors
