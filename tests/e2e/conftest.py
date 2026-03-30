"""VM E2E test fixtures.

Downloads a real Ubuntu ISO, builds a customized ISO with autoboot,
and provides it to tests that boot it in QEMU via Packer.

Run with: uv run pytest -m vm -s
"""

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from autoboot.build import build_iso, check_build_prerequisites
from autoboot.config import load_config
from autoboot.iso import download_iso

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _log(msg: str) -> None:
    """Print a timestamped progress message to stdout."""
    sys.stdout.write(f"\n  [E2E] {msg}\n")
    sys.stdout.flush()


def _check_kvm() -> bool:
    """Check if KVM acceleration is available."""
    return Path("/dev/kvm").exists()


@pytest.fixture(scope="session")
def ubuntu_iso():
    """Download real Ubuntu ISO (cached in isos/downloads)."""
    config = load_config(
        FIXTURES_DIR / "configs" / "e2e-ubuntu" / "config.yaml",
    )
    downloads_dir = PROJECT_ROOT / "isos" / "downloads"
    iso_path = downloads_dir / "ubuntu-24.04.3-live-server-amd64.iso"

    if iso_path.exists():
        size_mb = iso_path.stat().st_size / (1024 * 1024)
        _log(f"Using cached ISO: {iso_path.name} ({size_mb:.0f} MB)")
    else:
        _log("Downloading Ubuntu 24.04.3 ISO (~2.7 GB)...")

    result = download_iso(config, downloads_dir)
    _log(f"ISO ready: {result.name}")
    return result


@pytest.fixture(scope="session")
def built_ubuntu_iso(ubuntu_iso, tmp_path_factory):
    """Build a customized Ubuntu ISO from the real source ISO."""
    try:
        check_build_prerequisites()
    except RuntimeError:
        pytest.skip("xorriso not installed")

    _log(f"Building customized ISO from {ubuntu_iso.name}...")
    t0 = time.monotonic()

    config = load_config(
        FIXTURES_DIR / "configs" / "e2e-ubuntu" / "config.yaml",
    )
    ssh_key = (FIXTURES_DIR / "keys" / "ansible.pub").read_text().strip()

    output_dir = tmp_path_factory.mktemp("e2e-built")
    result = build_iso(
        config, ubuntu_iso, ssh_key,
        TEMPLATES_DIR, SCRIPTS_DIR, output_dir,
    )

    elapsed = time.monotonic() - t0
    size_mb = result.stat().st_size / (1024 * 1024)
    _log(f"Built ISO: {result.name} ({size_mb:.0f} MB) in {elapsed:.1f}s")
    return result


def _run_packer(
    template: Path, iso_path: Path, ssh_key_path: Path,
) -> subprocess.CompletedProcess:
    """Run packer build with live progress output."""
    _log("Initializing Packer plugins...")
    subprocess.run(
        ["packer", "init", str(template)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )

    kvm = _check_kvm()
    _log(
        f"Starting Packer build "
        f"(KVM: {'yes' if kvm else 'NO — will be slow!'})..."
    )
    _log(f"  ISO:      {iso_path.name}")
    _log(f"  Template: {template.name}")
    _log(
        "  The VM will boot, run a full Ubuntu install, "
        "then validate via SSH."
    )
    _log("  This typically takes 10-20 minutes with KVM.")

    t0 = time.monotonic()

    # Stream Packer output live so progress is visible
    process = subprocess.Popen(
        [
            "packer", "build",
            "-var", f"iso_path={iso_path}",
            "-var", f"ssh_private_key_file={ssh_key_path}",
            str(template),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    stdout_lines = []
    vnc_shown = False
    assert process.stdout is not None
    for line in process.stdout:
        stdout_lines.append(line)
        stripped = line.rstrip()
        if stripped:
            # Show VNC address so user can watch the install
            if "vnc://" in stripped and not vnc_shown:
                vnc_shown = True
                vnc_match = re.search(
                    r"vnc://(\S+):(\d+)", stripped,
                )
                if vnc_match:
                    host = vnc_match.group(1)
                    port = vnc_match.group(2)
                    _log(
                        f"  To watch the install: "
                        f"vncviewer {host}::{port}"
                    )

            # Show key Packer events as progress
            if any(
                kw in stripped for kw in (
                    "Waiting for SSH",
                    "Connected to SSH",
                    "Provisioning with",
                    "All checks passed",
                    "Build finished",
                    "Error",
                    "==>",
                )
            ):
                _log(f"  packer: {stripped}")

    process.wait()
    elapsed = time.monotonic() - t0

    stdout_text = "".join(stdout_lines)

    if process.returncode == 0:
        _log(f"Packer build succeeded in {elapsed:.0f}s")
    else:
        _log(f"Packer build FAILED after {elapsed:.0f}s")

    return subprocess.CompletedProcess(
        args=process.args,
        returncode=process.returncode,
        stdout=stdout_text,
        stderr="",
    )


@pytest.fixture(scope="session")
def packer_ubuntu_result(built_ubuntu_iso):
    """Run Packer to boot the Ubuntu ISO in QEMU and validate."""
    template = (
        PROJECT_ROOT / "tests" / "e2e" / "ubuntu-autoinstall.pkr.hcl"
    )
    ssh_key = FIXTURES_DIR / "keys" / "ansible"

    result = _run_packer(template, built_ubuntu_iso, ssh_key)

    # Clean up VM output
    output_dir = PROJECT_ROOT / "tests" / "e2e" / "output" / "ubuntu"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    return result
