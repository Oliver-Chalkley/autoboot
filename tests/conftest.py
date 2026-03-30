"""Root test configuration — markers, shared fixtures, skip logic."""

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"], capture_output=True, timeout=10, check=False,
    )
    return result.returncode == 0


def _packer_available() -> bool:
    return shutil.which("packer") is not None


def _qemu_available() -> bool:
    return shutil.which("qemu-system-x86_64") is not None


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def test_ssh_pubkey() -> str:
    return (FIXTURES_DIR / "keys" / "ansible.pub").read_text().strip()


@pytest.fixture(scope="session")
def test_ssh_private_key() -> Path:
    return FIXTURES_DIR / "keys" / "ansible"


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Auto-skip docker/vm tests if prerequisites are missing."""
    skip_docker = pytest.mark.skip(reason="Docker not available")
    skip_vm = pytest.mark.skip(reason="Packer or QEMU not available")

    docker_checked = None
    vm_checked = None

    for item in items:
        if "docker" in item.keywords:
            if docker_checked is None:
                docker_checked = _docker_available()
            if not docker_checked:
                item.add_marker(skip_docker)

        if "vm" in item.keywords:
            if vm_checked is None:
                vm_checked = _packer_available() and _qemu_available()
            if not vm_checked:
                item.add_marker(skip_vm)
