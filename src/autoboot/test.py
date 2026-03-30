"""VM test orchestration — boot ISO in QEMU via Packer, validate installation."""

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from autoboot.config import load_config
from autoboot.flash import find_latest_iso
from autoboot.paths import (
    get_built_dir,
    get_configs_dir,
    get_keys_dir,
    get_project_root,
)

_PACKER_TEMPLATES: dict[str, str] = {
    "ubuntu": "ubuntu-autoinstall.pkr.hcl",
    "debian": "debian-preseed.pkr.hcl",
}


@dataclass
class VmTestResult:
    """Result of a VM test run."""

    passed: bool
    output: str
    duration: float


def _log(msg: str) -> None:
    """Print a progress message to stdout."""
    sys.stdout.write(f"\n  [test] {msg}\n")
    sys.stdout.flush()


def check_test_prerequisites() -> None:
    """Check that packer and qemu-system-x86_64 are available."""
    missing = []
    if shutil.which("packer") is None:
        missing.append("packer")
    if shutil.which("qemu-system-x86_64") is None:
        missing.append("qemu-system-x86_64")

    if missing:
        tools = ", ".join(missing)
        msg = (
            f"Missing prerequisites: {tools}\n"
            "Install them to run VM tests:\n"
            "  packer:             https://www.packer.io/\n"
            "  qemu-system-x86_64: sudo apt install qemu-system-x86"
        )
        raise RuntimeError(msg)


def _check_kvm() -> bool:
    """Check if KVM acceleration is available."""
    return Path("/dev/kvm").exists()


def get_packer_template(distro: str, project_root: Path) -> Path:
    """Get the Packer template path for a distro.

    Args:
        distro: Distro name (ubuntu, debian).
        project_root: Project root directory.

    Returns:
        Path to the Packer .pkr.hcl template.
    """
    if distro not in _PACKER_TEMPLATES:
        available = ", ".join(sorted(_PACKER_TEMPLATES.keys()))
        msg = f"No test template for distro '{distro}'. Available: {available}"
        raise ValueError(msg)

    template = project_root / "tests" / "e2e" / _PACKER_TEMPLATES[distro]
    if not template.exists():
        msg = f"Packer template not found: {template}"
        raise FileNotFoundError(msg)

    return template


def run_vm_test(
    iso_path: Path,
    template: Path,
    ssh_key_path: Path,
    project_root: Path,
) -> VmTestResult:
    """Run Packer to boot an ISO in QEMU and validate the installation.

    Streams progress to stdout so the user can follow along.

    Args:
        iso_path: Path to the built ISO.
        template: Path to the Packer .pkr.hcl template.
        ssh_key_path: Path to the SSH private key for the ansible user.
        project_root: Project root (Packer cwd).

    Returns:
        VmTestResult with pass/fail, captured output, and duration.
    """
    _log("Initializing Packer plugins...")
    subprocess.run(
        ["packer", "init", str(template)],
        cwd=project_root,
        check=True,
        capture_output=True,
    )

    kvm = _check_kvm()
    _log(
        f"Starting VM test "
        f"(KVM: {'yes' if kvm else 'NO — will be slow!'})..."
    )
    _log(f"  ISO:      {iso_path.name}")
    _log(f"  Template: {template.name}")
    _log(
        "  The VM will boot, run a full install, "
        "then validate via SSH."
    )
    _log("  This typically takes 10-20 minutes with KVM.")

    t0 = time.monotonic()

    process = subprocess.Popen(
        [
            "packer", "build",
            "-var", f"iso_path={iso_path}",
            "-var", f"ssh_private_key_file={ssh_key_path}",
            str(template),
        ],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    stdout_lines: list[str] = []
    vnc_shown = False
    assert process.stdout is not None
    for line in process.stdout:
        stdout_lines.append(line)
        stripped = line.rstrip()
        if stripped:
            # Show VNC address so user can watch the install
            if "vnc://" in stripped and not vnc_shown:
                vnc_shown = True
                vnc_match = re.search(r"vnc://(\S+):(\d+)", stripped)
                if vnc_match:
                    host = vnc_match.group(1)
                    port = vnc_match.group(2)
                    _log(
                        f"To watch the install: vncviewer {host}::{port}"
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
    passed = process.returncode == 0

    if passed:
        _log(f"VM test PASSED in {elapsed:.0f}s")
    else:
        _log(f"VM test FAILED after {elapsed:.0f}s")

    return VmTestResult(passed=passed, output=stdout_text, duration=elapsed)


def _get_output_dir(distro: str, project_root: Path) -> Path:
    """Get the Packer VM output directory for a distro."""
    return project_root / "tests" / "e2e" / "output" / distro


def verify_machine(
    machine_name: str,
    root: Path | None = None,
) -> VmTestResult:
    """Test a machine's built ISO by booting it in a VM.

    Boots the most recent built ISO for the machine in QEMU via Packer,
    then validates the installation (ansible user, SSH, sudo, packages).

    Prerequisites: packer, qemu-system-x86_64, KVM recommended.

    Args:
        machine_name: Name of the machine config.
        root: Project root directory (auto-detected if None).

    Returns:
        VmTestResult with pass/fail, captured output, and duration.
    """
    check_test_prerequisites()

    project_root = root or get_project_root()

    # Load config to determine distro
    configs_dir = get_configs_dir(root)
    config_path = configs_dir / machine_name / "config.yaml"
    config = load_config(config_path)

    # Find the latest built ISO
    built_dir = get_built_dir(root)
    iso_path = find_latest_iso(machine_name, built_dir)
    if iso_path is None:
        msg = (
            f"No built ISO found for '{machine_name}'. "
            f"Run 'autoboot build {machine_name}' first."
        )
        raise FileNotFoundError(msg)

    # Find SSH private key
    keys_dir = get_keys_dir(root)
    ssh_key_path = keys_dir / "ansible"
    if not ssh_key_path.exists():
        msg = (
            f"SSH private key not found at {ssh_key_path}. "
            f"Place your ansible SSH private key there."
        )
        raise FileNotFoundError(msg)

    # Get Packer template for this distro
    template = get_packer_template(config.distro, project_root)

    # Clean up any previous VM output
    output_dir = _get_output_dir(config.distro, project_root)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    try:
        result = run_vm_test(iso_path, template, ssh_key_path, project_root)
    finally:
        # Clean up VM output (qcow2 disk image)
        output_dir = _get_output_dir(config.distro, project_root)
        if output_dir.exists():
            shutil.rmtree(output_dir)

    return result
