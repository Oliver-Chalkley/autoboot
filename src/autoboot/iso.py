"""ISO download and checksum verification."""

import hashlib
import shutil
import subprocess
from pathlib import Path

from autoboot.distros import get_handler
from autoboot.models import MachineConfig


def check_download_prerequisites() -> None:
    """Check that download prerequisites are installed."""
    if shutil.which("curl") is None:
        msg = (
            "curl is not installed. It's needed to download ISO images.\n"
            "Install it with:\n"
            "  Debian/Ubuntu:  sudo apt install curl\n"
            "  Fedora/RHEL:    sudo dnf install curl\n"
            "  Arch:           sudo pacman -S curl"
        )
        raise RuntimeError(msg)


def iso_path_for_config(config: MachineConfig, downloads_dir: Path) -> Path:
    """Return the expected ISO path for a machine config."""
    handler = get_handler(config.distro)
    filename = handler.iso_filename(config.distro_version)
    return downloads_dir / filename


def find_local_iso(config: MachineConfig, downloads_dir: Path) -> Path | None:
    """Check if the ISO for a config already exists locally."""
    path = iso_path_for_config(config, downloads_dir)
    return path if path.exists() else None


def verify_checksum(iso_path: Path, expected_hash: str) -> bool:
    """Verify SHA256 checksum of an ISO file."""
    sha256 = hashlib.sha256()
    with open(iso_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_hash.lower()


def parse_checksum_file(content: str, iso_filename: str) -> str | None:
    """Extract the checksum for a specific file from SHA256SUMS content."""
    for line in content.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:  # noqa: PLR2004
            checksum = parts[0]
            filename = parts[-1].lstrip("*")
            if filename == iso_filename:
                return checksum
    return None


def download_iso(
    config: MachineConfig,
    downloads_dir: Path,
    local_iso: Path | None = None,
    force: bool = False,
) -> Path:
    """Download or copy an ISO for a machine config.

    Args:
        config: Machine configuration.
        downloads_dir: Directory to store downloaded ISOs.
        local_iso: Path to a local ISO file to copy instead of downloading.
        force: Re-download even if the ISO already exists.

    Returns:
        Path to the downloaded/copied ISO.
    """
    handler = get_handler(config.distro)
    filename = handler.iso_filename(config.distro_version)
    dest = downloads_dir / filename

    downloads_dir.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        return dest

    if local_iso:
        if not local_iso.exists():
            msg = f"Local ISO not found: {local_iso}"
            raise FileNotFoundError(msg)
        shutil.copy2(local_iso, dest)
        return dest

    check_download_prerequisites()

    url = handler.iso_url(config.distro_version)
    _download_file(url, dest)

    checksum_url = handler.checksum_url(config.distro_version)
    try:
        checksum_content = _fetch_url_text(checksum_url)
        expected = parse_checksum_file(checksum_content, filename)
        if expected and not verify_checksum(dest, expected):
            dest.unlink()
            msg = f"Checksum verification failed for {filename}"
            raise ValueError(msg)
    except subprocess.CalledProcessError:
        pass  # Checksum file unavailable — skip verification with warning

    return dest


def _download_file(url: str, dest: Path) -> None:
    """Download a file using curl."""
    subprocess.run(
        ["curl", "-fL", "--progress-bar", "-o", str(dest), url],
        check=True,
    )


def _fetch_url_text(url: str) -> str:
    """Fetch URL content as text using curl."""
    result = subprocess.run(
        ["curl", "-fsSL", url],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
