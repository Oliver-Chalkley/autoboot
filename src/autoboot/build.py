"""ISO customization and build orchestration."""

import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from autoboot.config import load_config
from autoboot.distros import get_handler
from autoboot.iso import find_local_iso
from autoboot.models import MachineConfig
from autoboot.paths import (
    get_built_dir,
    get_configs_dir,
    get_downloads_dir,
    get_scripts_dir,
    get_ssh_public_key,
    get_templates_dir,
)


def check_build_prerequisites() -> None:
    """Check that build prerequisites are installed."""
    if shutil.which("xorriso") is None:
        msg = (
            "xorriso is not installed. It's needed to repack ISO images.\n"
            "Install it with:\n"
            "  Debian/Ubuntu:  sudo apt install xorriso\n"
            "  Fedora/RHEL:    sudo dnf install xorriso\n"
            "  Arch:           sudo pacman -S libisoburn"
        )
        raise RuntimeError(msg)


def render_installer_config(
    config: MachineConfig, ssh_key: str, templates_dir: Path
) -> dict[str, str]:
    """Render distro-specific installer config files."""
    handler = get_handler(config.distro)
    rendered = handler.render_config(config, ssh_key, templates_dir)

    errors = handler.validate_rendered_config(rendered)
    if errors:
        msg = f"Rendered config validation failed: {'; '.join(errors)}"
        raise ValueError(msg)

    return rendered


def build_iso(  # noqa: PLR0913
    config: MachineConfig,
    source_iso: Path,
    ssh_key: str,
    templates_dir: Path,
    scripts_dir: Path,
    output_dir: Path,
) -> Path:
    """Build a customized ISO for a machine config.

    Returns:
        Path to the built ISO.
    """
    handler = get_handler(config.distro)
    rendered = render_installer_config(config, ssh_key, templates_dir)

    date_str = datetime.now(tz=UTC).strftime("%Y%m%d")
    output_iso = output_dir / f"{config.machine_name}-{date_str}.iso"
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="autoboot-") as tmpdir:
        config_dir = Path(tmpdir) / "config"
        for rel_path, content in rendered.items():
            file_path = config_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        # Determine the injection path (top-level directory from rendered paths)
        first_path = next(iter(rendered.keys()))
        if "/" in first_path:
            injection_path = first_path.split("/")[0]
            # Config dir should contain the files without the injection path prefix
            actual_config_dir = config_dir / injection_path
        else:
            injection_path = "."
            actual_config_dir = config_dir

        build_script = scripts_dir / "build-iso.sh"
        subprocess.run(
            [
                str(build_script),
                "--source-iso", str(source_iso),
                "--output-iso", str(output_iso),
                "--config-dir", str(actual_config_dir),
                "--injection-path", injection_path,
                "--grub-sed", handler.grub_sed_pattern(),
            ],
            check=True,
        )

    return output_iso


def build_machine(
    machine_name: str,
    root: Path | None = None,
    source_iso: Path | None = None,
) -> Path:
    """High-level build function: load config, find ISO, build.

    Returns:
        Path to the built ISO.
    """
    check_build_prerequisites()

    configs_dir = get_configs_dir(root)
    config_path = configs_dir / machine_name / "config.yaml"
    config = load_config(config_path)

    ssh_key = get_ssh_public_key(root)
    templates_dir = get_templates_dir(root)
    scripts_dir = get_scripts_dir(root)
    output_dir = get_built_dir(root)

    if source_iso is None:
        downloads_dir = get_downloads_dir(root)
        source_iso = find_local_iso(config, downloads_dir)
        if source_iso is None:
            msg = (
                f"No ISO found for {config.distro} {config.distro_version}. "
                f"Run 'autoboot download {machine_name}' first."
            )
            raise FileNotFoundError(msg)

    return build_iso(
        config, source_iso, ssh_key, templates_dir, scripts_dir, output_dir,
    )
