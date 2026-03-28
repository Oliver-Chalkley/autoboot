"""Tests for autoboot.paths module."""

from pathlib import Path

import pytest

from autoboot.paths import (
    get_built_dir,
    get_configs_dir,
    get_downloads_dir,
    get_isos_dir,
    get_keys_dir,
    get_project_root,
    get_scripts_dir,
    get_ssh_public_key,
    get_templates_dir,
)


def test_get_project_root_finds_pyproject():
    root = get_project_root()
    assert (root / "pyproject.toml").exists()


def test_get_configs_dir_with_root(tmp_path: Path):
    result = get_configs_dir(tmp_path)
    assert result == tmp_path / "configs"


def test_get_keys_dir_with_root(tmp_path: Path):
    result = get_keys_dir(tmp_path)
    assert result == tmp_path / "keys"


def test_get_isos_dir_with_root(tmp_path: Path):
    result = get_isos_dir(tmp_path)
    assert result == tmp_path / "isos"


def test_get_downloads_dir_with_root(tmp_path: Path):
    result = get_downloads_dir(tmp_path)
    assert result == tmp_path / "isos" / "downloads"


def test_get_built_dir_with_root(tmp_path: Path):
    result = get_built_dir(tmp_path)
    assert result == tmp_path / "isos" / "built"


def test_get_templates_dir_with_root(tmp_path: Path):
    result = get_templates_dir(tmp_path)
    assert result == tmp_path / "templates"


def test_get_scripts_dir_with_root(tmp_path: Path):
    result = get_scripts_dir(tmp_path)
    assert result == tmp_path / "scripts"


def test_get_ssh_public_key_reads_file(tmp_path: Path):
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    key_file = keys_dir / "ansible.pub"
    key_file.write_text("ssh-ed25519 AAAA... ansible@server\n")

    result = get_ssh_public_key(tmp_path)
    assert result == "ssh-ed25519 AAAA... ansible@server"


def test_get_ssh_public_key_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="SSH public key not found"):
        get_ssh_public_key(tmp_path)
