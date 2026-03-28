"""Tests for autoboot.iso module."""

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from autoboot.iso import (
    check_download_prerequisites,
    download_iso,
    find_local_iso,
    iso_path_for_config,
    parse_checksum_file,
    verify_checksum,
)
from autoboot.models import AdminConfig, MachineConfig


def make_config(distro="ubuntu", version="24.04.3") -> MachineConfig:
    return MachineConfig(
        machine_name="test",
        distro=distro,
        distro_version=version,
        admin=AdminConfig(username="admin", password_hash="$6$hash"),
    )


class TestIsoPathForConfig:
    def test_ubuntu(self, tmp_path: Path):
        config = make_config("ubuntu", "24.04.3")
        path = iso_path_for_config(config, tmp_path)
        assert path == tmp_path / "ubuntu-24.04.3-live-server-amd64.iso"

    def test_debian(self, tmp_path: Path):
        config = make_config("debian", "12.9")
        path = iso_path_for_config(config, tmp_path)
        assert path == tmp_path / "debian-12.9-amd64-netinst.iso"


class TestFindLocalIso:
    def test_found(self, tmp_path: Path):
        config = make_config()
        iso = tmp_path / "ubuntu-24.04.3-live-server-amd64.iso"
        iso.write_bytes(b"fake iso")

        result = find_local_iso(config, tmp_path)
        assert result == iso

    def test_not_found(self, tmp_path: Path):
        config = make_config()
        result = find_local_iso(config, tmp_path)
        assert result is None


class TestVerifyChecksum:
    def test_valid_checksum(self, tmp_path: Path):
        test_file = tmp_path / "test.iso"
        content = b"test content for checksum"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert verify_checksum(test_file, expected) is True

    def test_invalid_checksum(self, tmp_path: Path):
        test_file = tmp_path / "test.iso"
        test_file.write_bytes(b"test content")

        assert verify_checksum(test_file, "deadbeef" * 8) is False

    def test_case_insensitive(self, tmp_path: Path):
        test_file = tmp_path / "test.iso"
        content = b"test"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest().upper()
        assert verify_checksum(test_file, expected) is True


class TestParseChecksumFile:
    def test_finds_matching_file(self):
        content = (
            "abc123  ubuntu-24.04.3-live-server-amd64.iso\n"
            "def456  ubuntu-24.04.3-desktop-amd64.iso\n"
        )
        result = parse_checksum_file(content, "ubuntu-24.04.3-live-server-amd64.iso")
        assert result == "abc123"

    def test_handles_star_prefix(self):
        content = "abc123 *ubuntu-24.04.3-live-server-amd64.iso\n"
        result = parse_checksum_file(content, "ubuntu-24.04.3-live-server-amd64.iso")
        assert result == "abc123"

    def test_returns_none_for_missing(self):
        content = "abc123  other-file.iso\n"
        result = parse_checksum_file(content, "target.iso")
        assert result is None

    def test_empty_content(self):
        result = parse_checksum_file("", "target.iso")
        assert result is None


class TestCheckDownloadPrerequisites:
    def test_passes_when_curl_available(self):
        with patch("autoboot.iso.shutil.which", return_value="/usr/bin/curl"):
            check_download_prerequisites()  # should not raise

    def test_raises_when_curl_missing(self):
        with patch("autoboot.iso.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="curl is not installed"):
                check_download_prerequisites()


class TestDownloadIso:
    def test_returns_existing_iso(self, tmp_path: Path):
        config = make_config()
        iso = tmp_path / "ubuntu-24.04.3-live-server-amd64.iso"
        iso.write_bytes(b"existing")

        result = download_iso(config, tmp_path)
        assert result == iso

    def test_force_redownloads(self, tmp_path: Path):
        config = make_config()
        iso = tmp_path / "ubuntu-24.04.3-live-server-amd64.iso"
        iso.write_bytes(b"old")

        with patch("autoboot.iso._download_file") as mock_dl, \
             patch(
                 "autoboot.iso._fetch_url_text",
                 side_effect=subprocess.CalledProcessError(1, "curl"),
             ):
            mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"new")
            download_iso(config, tmp_path, force=True)
            assert mock_dl.called

    def test_copies_local_iso(self, tmp_path: Path):
        config = make_config()
        local = tmp_path / "source" / "my.iso"
        local.parent.mkdir()
        local.write_bytes(b"local iso content")

        dest_dir = tmp_path / "downloads"
        result = download_iso(config, dest_dir, local_iso=local)
        assert result.exists()
        assert result.read_bytes() == b"local iso content"

    def test_local_iso_not_found_raises(self, tmp_path: Path):
        config = make_config()
        with pytest.raises(FileNotFoundError, match="Local ISO not found"):
            download_iso(config, tmp_path, local_iso=tmp_path / "nope.iso")

    @patch("autoboot.iso._download_file")
    @patch("autoboot.iso._fetch_url_text")
    def test_downloads_and_verifies(self, mock_fetch, mock_dl, tmp_path: Path):
        config = make_config()
        content = b"downloaded iso"
        expected_hash = hashlib.sha256(content).hexdigest()

        mock_dl.side_effect = lambda url, dest: dest.write_bytes(content)
        mock_fetch.return_value = (
            f"{expected_hash}  ubuntu-24.04.3-live-server-amd64.iso\n"
        )

        result = download_iso(config, tmp_path, force=True)
        assert result.exists()
        assert result.read_bytes() == content

    @patch("autoboot.iso._download_file")
    @patch("autoboot.iso._fetch_url_text")
    def test_bad_checksum_deletes_file(self, mock_fetch, mock_dl, tmp_path: Path):
        config = make_config()

        mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"bad content")
        mock_fetch.return_value = (
            f"{'a' * 64}  ubuntu-24.04.3-live-server-amd64.iso\n"
        )

        with pytest.raises(ValueError, match="Checksum verification failed"):
            download_iso(config, tmp_path, force=True)

        iso = tmp_path / "ubuntu-24.04.3-live-server-amd64.iso"
        assert not iso.exists()
