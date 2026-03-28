"""Ubuntu autoinstall distro handler."""

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from autoboot.models import MachineConfig


class UbuntuHandler:
    """Handler for Ubuntu autoinstall-based installations."""

    @property
    def name(self) -> str:
        return "ubuntu"

    @property
    def supported_versions(self) -> list[str]:
        return ["24.04", "24.04.1", "24.04.2", "24.04.3"]

    def iso_url(self, version: str, arch: str = "amd64") -> str:
        return (
            f"https://releases.ubuntu.com/{version}/"
            f"ubuntu-{version}-live-server-{arch}.iso"
        )

    def checksum_url(self, version: str, arch: str = "amd64") -> str:
        return f"https://releases.ubuntu.com/{version}/SHA256SUMS"

    def iso_filename(self, version: str, arch: str = "amd64") -> str:
        return f"ubuntu-{version}-live-server-{arch}.iso"

    def render_config(
        self, config: MachineConfig, ssh_key: str, templates_dir: Path
    ) -> dict[str, str]:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir / "ubuntu")),
            keep_trailing_newline=True,
        )

        user_data_template = env.get_template("user-data.yaml.j2")
        meta_data_template = env.get_template("meta-data.j2")

        user_data = user_data_template.render(
            config=config,
            ssh_key=ssh_key,
        )
        meta_data = meta_data_template.render(config=config)

        return {
            "nocloud/user-data": user_data,
            "nocloud/meta-data": meta_data,
        }

    def grub_sed_pattern(self) -> str:
        return r"s|---|autoinstall ds=nocloud\\;s=/cdrom/nocloud/ ---|g"

    def validate_rendered_config(self, rendered: dict[str, str]) -> list[str]:
        errors = []
        if "nocloud/user-data" not in rendered:
            errors.append("Missing nocloud/user-data in rendered config.")
            return errors

        user_data = rendered["nocloud/user-data"]
        try:
            parsed = yaml.safe_load(user_data)
        except yaml.YAMLError as e:
            errors.append(f"user-data is not valid YAML: {e}")
            return errors

        if not isinstance(parsed, dict):
            errors.append("user-data must be a YAML mapping.")
            return errors

        if "autoinstall" not in parsed:
            errors.append("user-data must contain 'autoinstall' key.")

        return errors
