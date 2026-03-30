# Autoboot

Create bootable USBs that auto-install Linux with an ansible user and SSH key, ready for remote management.

Write a simple YAML config per machine. Autoboot renders it into the correct distro-specific installer format (Ubuntu autoinstall or Debian preseed), builds a customized ISO, and flashes it to USB.

## Why

When a USB stick is lost or a new machine needs provisioning, you need to recreate an exact bootable USB quickly. Manual installs are slow and error-prone. Autoboot makes it reproducible — configs are version-controlled, ISOs are rebuilt from official sources.

## Prerequisites

You need a few system packages alongside Python. Install what you're missing:

**Debian / Ubuntu:**
```bash
sudo apt install xorriso curl
```

**Fedora / RHEL:**
```bash
sudo dnf install xorriso curl
```

**Arch:**
```bash
sudo pacman -S libisoburn curl
```

You also need [uv](https://docs.astral.sh/uv/) for Python dependency management.

## Quick Start

```bash
uv sync

# Add your SSH public key (the one your ansible controller will use)
cp ~/.ssh/my_key.pub keys/ansible.pub

# Create a machine config
uv run autoboot new my-server --distro ubuntu

# Edit the config — set hostname, password hash, network, etc.
nano configs/my-server/config.yaml

# Download the official ISO
uv run autoboot download my-server

# Build a customized ISO with your config baked in
uv run autoboot build my-server

# (Optional) Test the ISO in a VM before flashing
uv run autoboot test my-server

# Flash to USB (requires root)
sudo uv run autoboot flash my-server /dev/sdb
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `autoboot list` | List all machine configs |
| `autoboot new <name> --distro <distro>` | Create a new machine config |
| `autoboot validate <name>` | Validate a machine config |
| `autoboot download <name>` | Download the ISO for a machine |
| `autoboot build <name>` | Build a customized ISO |
| `autoboot test <name>` | Test a built ISO in a VM |
| `autoboot flash <name> <device>` | Flash a built ISO to USB |

### Options

- `--version` — Show version
- `--root PATH` — Override project root directory
- `download --force` — Re-download even if ISO exists
- `download --local PATH` — Copy ISO from local path (e.g., NAS) instead of downloading
- `test` — Boot built ISO in a VM and validate install. Requires `packer`, `qemu-system-x86_64`. KVM recommended (~10-20 min)
- `flash --yes` — Skip confirmation prompt

## Machine Config

Configs live in `configs/<name>/config.yaml`:

```yaml
machine_name: my-server
distro: ubuntu
distro_version: "24.04.3"
hostname: my-server
locale: en_US.UTF-8
keyboard_layout: us
timezone: UTC

network:
  type: dhcp              # or "static" with address/gateway/dns

storage:
  layout: lvm             # or "direct"
  match: largest

admin:
  username: admin
  password_hash: "$6$..."  # Generate with: mkpasswd -m sha-512
  real_name: Administrator

packages: []              # Extra packages beyond python3, openssh-server
extra_late_commands: []    # Extra post-install commands
```

The simple YAML is rendered into distro-specific format (autoinstall YAML for Ubuntu, preseed.cfg for Debian) via Jinja2 templates. You don't need to understand cloud-init or preseed syntax.

## Supported Distros

| Distro | Mechanism | Versions |
|--------|-----------|----------|
| Ubuntu | autoinstall (cloud-init) | 24.04, 24.04.1, 24.04.2, 24.04.3 |
| Debian | preseed (debconf) | 12.8, 12.9, 12.10 |

Adding a new distro requires implementing a handler class in `src/autoboot/distros/` and a Jinja2 template in `templates/`.

## What Gets Installed

Every machine gets:
- The configured admin user with password
- An `ansible` user with your SSH public key and passwordless sudo
- `python3`, `openssh-server`, and any extra packages you specify
- Network configured (DHCP or static)
- LVM or direct storage layout

## Project Structure

```
src/autoboot/          # Python package
  cli.py               # Click CLI
  models.py            # Config dataclasses
  config.py            # Config CRUD + validation
  iso.py               # ISO download + checksum verification
  build.py             # ISO build orchestration
  test.py              # VM test orchestration (Packer+QEMU)
  flash.py             # USB flash orchestration
  distros/             # Distro handler implementations
templates/             # Jinja2 templates for installer configs
scripts/               # Bash scripts (build-iso.sh, flash-usb.sh)
configs/               # Machine configs (version-controlled)
keys/                  # SSH public key for ansible user
isos/                  # Downloaded and built ISOs (gitignored)
tests/
  unit/                # Fast pytest tests (<1s)
  docker/              # Docker ISO build tests (~10s)
  e2e/                 # VM E2E tests via Packer+QEMU (~10min)
  fixtures/            # Test SSH keys and configs (committed)
  integration/         # Config round-trip tests
  bats/                # BATS tests for bash scripts
```

## Development

```bash
uv sync                           # Install dependencies
uv run ruff check .               # Lint
uv run pyright                    # Type check
shellcheck scripts/*.sh           # Bash lint
```

## Testing

Three tiers, from fast to thorough:

### Unit + integration tests (fast, <1s)

```bash
uv run pytest
```

Runs 169 tests covering config validation, template rendering, CLI parsing, and more. No external tools needed beyond Python.

### Docker integration tests (~10s)

```bash
uv run pytest -m docker
```

Builds real ISOs inside Docker (with xorriso), using small fake source ISOs. Verifies config files are injected, GRUB is modified, SSH keys are present. **Requires:** Docker.

### VM end-to-end tests (~10 min)

```bash
uv run pytest -m vm -s
```

Downloads a real Ubuntu 24.04.3 ISO, builds a customized ISO, boots it in a QEMU VM via Packer, and validates the full installation (ansible user, SSH key, sudo, packages). **Requires:** `packer`, `qemu-system-x86_64`, `xorriso`, `curl`, KVM, ~3GB disk.

Test fixtures (SSH keypair, Ubuntu config) are committed at `tests/fixtures/` so everything runs straight from clone — no manual setup needed.

Use `-s` to see live progress. The output includes a VNC command to watch the install:
```
  [E2E] To watch the install: vncviewer 127.0.0.1::5941
```

### Test before flashing

After building an ISO, you can verify it works by booting it in a VM before committing to a real USB:

```bash
uv run autoboot test my-server
```

This boots the built ISO in QEMU via Packer, waits for the install to complete, then connects via SSH and validates: ansible user exists, SSH key works, passwordless sudo, python3 and openssh-server installed. Takes ~10-20 minutes with KVM. Progress is streamed to stdout, including a VNC command to watch the install live.

**Requires:** `packer`, `qemu-system-x86_64`, KVM recommended.

### Validate an existing machine

Run the Ansible playbook directly against a machine you've already installed:
```bash
ansible-playbook -i 192.168.1.100, -u ansible \
    --private-key tests/fixtures/keys/ansible \
    tests/e2e/validate-install.yml
```
