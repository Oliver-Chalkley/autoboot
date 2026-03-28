"""USB flash orchestration."""

import shutil
import subprocess
from pathlib import Path

from autoboot.paths import get_built_dir, get_scripts_dir


def check_flash_prerequisites() -> None:
    """Check that flash prerequisites are installed."""
    if shutil.which("dd") is None:
        msg = (
            "dd is not installed. It's needed to write ISOs to USB devices.\n"
            "It should be part of coreutils — something is very wrong if "
            "it's missing."
        )
        raise RuntimeError(msg)


def find_latest_iso(machine_name: str, built_dir: Path) -> Path | None:
    """Find the most recent built ISO for a machine.

    Returns:
        Path to the latest ISO, or None if no ISOs found.
    """
    pattern = f"{machine_name}-*.iso"
    isos = sorted(built_dir.glob(pattern))
    return isos[-1] if isos else None


def validate_device(device: Path) -> list[str]:
    """Validate a block device path.

    Returns:
        List of error messages (empty if valid).
    """
    errors = []
    if not device.exists():
        errors.append(f"Device not found: {device}")
    elif not device.is_block_device():
        errors.append(f"Not a block device: {device}")

    # Refuse whole-disk devices that look like system drives
    name = device.name
    if name in ("sda", "nvme0n1", "vda"):
        errors.append(
            f"Refusing to write to {device} — looks like a system drive. "
            f"Use a specific device like /dev/sdb."
        )

    return errors


def flash_iso(
    iso_path: Path,
    device: Path,
    scripts_dir: Path,
    skip_confirm: bool = False,
) -> None:
    """Flash an ISO to a USB device.

    Args:
        iso_path: Path to the ISO file.
        device: Block device to write to.
        scripts_dir: Directory containing flash-usb.sh.
        skip_confirm: Skip the interactive confirmation prompt.
    """
    if not iso_path.exists():
        msg = f"ISO not found: {iso_path}"
        raise FileNotFoundError(msg)

    errors = validate_device(device)
    if errors:
        msg = "; ".join(errors)
        raise ValueError(msg)

    flash_script = scripts_dir / "flash-usb.sh"
    cmd = [
        str(flash_script),
        "--iso", str(iso_path),
        "--device", str(device),
    ]
    if skip_confirm:
        cmd.append("--yes")

    subprocess.run(cmd, check=True)


def flash_machine(
    machine_name: str,
    device: Path,
    root: Path | None = None,
    skip_confirm: bool = False,
) -> None:
    """High-level flash function: find latest ISO and flash it.

    Args:
        machine_name: Name of the machine config.
        device: Block device to write to.
        root: Project root directory.
        skip_confirm: Skip the interactive confirmation prompt.
    """
    check_flash_prerequisites()

    built_dir = get_built_dir(root)
    scripts_dir = get_scripts_dir(root)

    iso_path = find_latest_iso(machine_name, built_dir)
    if iso_path is None:
        msg = (
            f"No built ISO found for '{machine_name}'. "
            f"Run 'autoboot build {machine_name}' first."
        )
        raise FileNotFoundError(msg)

    flash_iso(iso_path, device, scripts_dir, skip_confirm)
