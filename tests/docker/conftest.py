"""Docker integration test fixtures.

Builds ISOs inside Docker (with xorriso) using a minimal fake source ISO,
then extracts the output for inspection. Each distro builds once per module.
"""

import subprocess
from pathlib import Path

import pytest

from autoboot.build import render_installer_config
from autoboot.distros import get_handler
from autoboot.models import AdminConfig, MachineConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "templates"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
DOCKER_IMAGE = "autoboot-test-build"


@pytest.fixture(scope="session")
def docker_image():
    """Build the Docker test image (once per session)."""
    subprocess.run(
        [
            "docker",
            "build",
            "-t",
            DOCKER_IMAGE,
            "-f",
            str(PROJECT_ROOT / "tests" / "docker" / "Dockerfile"),
            str(PROJECT_ROOT),
        ],
        check=True,
        capture_output=True,
    )
    return DOCKER_IMAGE


def _build_and_extract(
    docker_image: str,
    tmp_path_factory: pytest.TempPathFactory,
    distro: str,
    version: str,
) -> Path:
    """Render config, build ISO in Docker with fake source, extract contents."""
    work_dir = tmp_path_factory.mktemp(f"docker-{distro}")

    config = MachineConfig(
        machine_name=f"test-{distro}",
        distro=distro,
        distro_version=version,
        admin=AdminConfig(
            username="ansible",
            password_hash="$6$test$hash",
        ),
    )

    ssh_key = (FIXTURES_DIR / "keys" / "ansible.pub").read_text().strip()
    handler = get_handler(distro)
    rendered = render_installer_config(config, ssh_key, TEMPLATES_DIR)

    # Determine injection path (same logic as build.py)
    first_path = next(iter(rendered.keys()))
    if "/" in first_path:
        injection_path = first_path.split("/")[0]
    else:
        injection_path = "."

    # Write rendered config files to work dir
    config_dir = work_dir / "config"
    for rel_path, content in rendered.items():
        file_path = config_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    # Create fake source ISO root with a GRUB config
    iso_root = work_dir / "iso-root" / "boot" / "grub"
    iso_root.mkdir(parents=True)

    if distro == "ubuntu":
        grub_content = (
            'menuentry "Install Ubuntu Server" {\n'
            "    linux /casper/vmlinuz --- quiet\n"
            "}\n"
        )
    elif distro == "fedora":
        grub_content = (
            'menuentry "Install Fedora" {\n'
            "    linuxefi /images/pxeboot/vmlinuz quiet\n"
            "}\n"
        )
    else:
        grub_content = 'menuentry "Install" {\n    linux /install --- quiet\n}\n'
    (iso_root / "grub.cfg").write_text(grub_content)

    # Determine the config dir to pass to build-iso.sh
    if injection_path != ".":
        actual_config_dir = f"/work/config/{injection_path}"
    else:
        actual_config_dir = "/work/config"

    (work_dir / "output").mkdir()

    grub_sed = handler.grub_sed_pattern()

    script = (
        "set -e\n"
        "xorriso -as mkisofs -r -V FAKE -o /work/source.iso"
        " /work/iso-root 2>/dev/null\n"
        "bash /work/scripts/build-iso.sh"
        " --source-iso /work/source.iso"
        " --output-iso /work/output/built.iso"
        f" --config-dir {actual_config_dir}"
        f" --injection-path {injection_path}"
        f" --grub-sed '{grub_sed}'\n"
        "mkdir -p /work/output/extracted\n"
        "xorriso -osirrox on -indev /work/output/built.iso"
        " -extract / /work/output/extracted 2>/dev/null\n"
        "chmod -R 777 /work/output\n"
    )

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{work_dir}:/work",
            "-v",
            f"{PROJECT_ROOT}/scripts:/work/scripts:ro",
            docker_image,
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            f"Docker ISO build failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    extracted = work_dir / "output" / "extracted"
    if not extracted.exists():
        pytest.fail("Extracted directory not found after Docker build")
    return extracted


@pytest.fixture(scope="module")
def ubuntu_iso_contents(docker_image, tmp_path_factory):
    """Build Ubuntu ISO in Docker and return path to extracted contents."""
    return _build_and_extract(docker_image, tmp_path_factory, "ubuntu", "24.04.3")


@pytest.fixture(scope="module")
def debian_iso_contents(docker_image, tmp_path_factory):
    """Build Debian ISO in Docker and return path to extracted contents."""
    return _build_and_extract(docker_image, tmp_path_factory, "debian", "12.9")


@pytest.fixture(scope="module")
def fedora_iso_contents(docker_image, tmp_path_factory):
    """Build Fedora ISO in Docker and return path to extracted contents."""
    return _build_and_extract(docker_image, tmp_path_factory, "fedora", "43")
