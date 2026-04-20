"""Tests for the distro handler registry."""

import pytest

from autoboot.distros import get_handler, list_distros
from autoboot.distros.base import DistroHandler
from autoboot.distros.debian import DebianHandler
from autoboot.distros.fedora import FedoraHandler
from autoboot.distros.ubuntu import UbuntuHandler


def test_list_distros():
    distros = list_distros()
    assert "ubuntu" in distros
    assert "debian" in distros
    assert "fedora" in distros


def test_get_handler_ubuntu():
    handler = get_handler("ubuntu")
    assert isinstance(handler, UbuntuHandler)
    assert isinstance(handler, DistroHandler)


def test_get_handler_debian():
    handler = get_handler("debian")
    assert isinstance(handler, DebianHandler)
    assert isinstance(handler, DistroHandler)


def test_get_handler_fedora():
    handler = get_handler("fedora")
    assert isinstance(handler, FedoraHandler)
    assert isinstance(handler, DistroHandler)


def test_get_handler_unknown_raises():
    with pytest.raises(ValueError, match="Unknown distro 'arch'"):
        get_handler("arch")


def test_get_handler_error_lists_available():
    with pytest.raises(ValueError, match="debian.*fedora.*ubuntu"):
        get_handler("nonexistent")
