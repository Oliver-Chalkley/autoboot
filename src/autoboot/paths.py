"""Project path constants and resolution."""

from pathlib import Path


def get_project_root() -> Path:
    """Find the project root by looking for pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    msg = "Could not find project root (no pyproject.toml found)"
    raise FileNotFoundError(msg)


def get_configs_dir(root: Path | None = None) -> Path:
    """Return the configs directory."""
    return (root or get_project_root()) / "configs"


def get_keys_dir(root: Path | None = None) -> Path:
    """Return the keys directory."""
    return (root or get_project_root()) / "keys"


def get_isos_dir(root: Path | None = None) -> Path:
    """Return the isos directory."""
    return (root or get_project_root()) / "isos"


def get_downloads_dir(root: Path | None = None) -> Path:
    """Return the ISO downloads directory."""
    return get_isos_dir(root) / "downloads"


def get_built_dir(root: Path | None = None) -> Path:
    """Return the built ISOs directory."""
    return get_isos_dir(root) / "built"


def get_templates_dir(root: Path | None = None) -> Path:
    """Return the templates directory."""
    return (root or get_project_root()) / "templates"


def get_scripts_dir(root: Path | None = None) -> Path:
    """Return the scripts directory."""
    return (root or get_project_root()) / "scripts"


def get_ssh_public_key(root: Path | None = None) -> str:
    """Read the ansible SSH public key."""
    key_path = get_keys_dir(root) / "ansible.pub"
    if not key_path.exists():
        msg = f"SSH public key not found at {key_path}"
        raise FileNotFoundError(msg)
    return key_path.read_text().strip()
