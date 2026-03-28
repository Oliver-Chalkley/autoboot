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
| `autoboot flash <name> <device>` | Flash a built ISO to USB |

### Options

- `--version` — Show version
- `--root PATH` — Override project root directory
- `download --force` — Re-download even if ISO exists
- `download --local PATH` — Copy ISO from local path (e.g., NAS) instead of downloading
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
  flash.py             # USB flash orchestration
  distros/             # Distro handler implementations
templates/             # Jinja2 templates for installer configs
scripts/               # Bash scripts (build-iso.sh, flash-usb.sh)
configs/               # Machine configs (version-controlled)
keys/                  # SSH public key for ansible user
isos/                  # Downloaded and built ISOs (gitignored)
```

## Development

```bash
uv sync                           # Install dependencies
uv run pytest tests/unit/         # Unit tests (fast, ~0.3s)
uv run pytest                     # All tests
uv run ruff check .               # Lint
uv run pyright                    # Type check
shellcheck scripts/*.sh           # Bash lint
```

## E2E Testing

The full end-to-end test boots a VM from a built ISO and validates the installation with Ansible. It takes ~15-30 minutes per distro.

**Extra prerequisites:** `packer`, `qemu-system-x86_64`, `ansible`

**Step 1 — Generate a test SSH keypair** (no passphrase):
```bash
ssh-keygen -t ed25519 -f keys/ansible -N ''
```

**Step 2 — Build a test ISO:**
```bash
uv run autoboot new e2e-test --distro ubuntu
uv run autoboot download e2e-test
uv run autoboot build e2e-test
```

**Step 3 — Initialize and run Packer:**
```bash
packer init tests/e2e/ubuntu-autoinstall.pkr.hcl
packer build \
    -var "iso_path=isos/built/e2e-test-$(date +%Y%m%d).iso" \
    -var "ssh_private_key_file=keys/ansible" \
    tests/e2e/ubuntu-autoinstall.pkr.hcl
```

Packer boots the ISO in a QEMU VM, waits for the install to finish and SSH to come up, then runs smoke tests and the Ansible validation playbook (`tests/e2e/validate-install.yml`).

Replace `ubuntu-autoinstall.pkr.hcl` with `debian-preseed.pkr.hcl` to test Debian.

**Step 4 — Or validate an existing machine** (skip Packer, run Ansible directly):
```bash
ansible-playbook -i 192.168.1.100, -u ansible \
    --private-key keys/ansible \
    tests/e2e/validate-install.yml
```
