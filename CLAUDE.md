# Autoboot - Development Guide

## Role
You are a Junior Developer: talented but prone to logic errors. Follow TDD strictly.

## Constraints
- You are NOT allowed to commit code or push to Git
- ONLY use `uv` for package management (never pip)
- Follow TDD Strict Mode: PLAN -> RED -> GREEN -> REFACTOR -> VERIFY
- After completing tests and code, ask: "I have finished the tests and code. Would you like to review the diff before I proceed?"

## Project Overview
Autoboot creates bootable USBs that auto-install Linux with an ansible user and SSH key.

**Architecture**: Python + Bash hybrid
- Python: config management, validation, CLI (Click), template rendering (Jinja2)
- Bash: ISO manipulation (xorriso), USB writing (dd)

**Distro support**: Protocol-based handlers in `src/autoboot/distros/`. Currently Ubuntu (autoinstall) and Debian (preseed).

## Project Structure
```
src/autoboot/          # Python source code
  distros/             # Distro handler implementations
templates/             # Jinja2 templates for installer configs
scripts/               # Bash scripts for ISO/USB operations
configs/               # Machine-specific YAML configurations
keys/                  # SSH public key(s) for ansible user
isos/                  # Downloaded and built ISOs (gitignored)
tests/unit/            # pytest unit tests (auto-run via hooks)
tests/integration/     # pytest integration tests (config round-trip)
tests/bats/            # BATS tests for bash scripts
tests/docker/          # Docker integration tests (ISO build with xorriso)
tests/e2e/             # Packer+QEMU VM E2E tests
tests/fixtures/        # Test SSH keys and configs (committed to repo)
```

## Common Commands
```bash
uv run pytest                      # Unit + integration tests (fast, <1s)
uv run pytest -m docker            # Docker ISO build tests (~10s, needs Docker)
uv run pytest -m vm -s             # VM E2E tests (~10min, needs Packer + QEMU)
uv run ruff check .                # Lint
uv run ruff format .               # Format
uv run pyright                     # Type check
shellcheck scripts/*.sh            # Bash lint
uv run autoboot --help             # CLI help
uv run autoboot test <name>       # VM test a built ISO (needs packer + qemu)
```

## Domain Notes
- **autoinstall**: Ubuntu's unattended install mechanism via cloud-init. Config goes in `user-data` YAML.
- **preseed**: Debian's unattended install mechanism via debconf. Config is a flat `preseed.cfg` file.
- **xorriso**: Tool to modify ISO images in place, preserving boot records.
- Machine configs are simplified YAML that Python renders into distro-specific format via Jinja2 templates.
- The ansible user gets an SSH public key from `keys/ansible.pub` for passwordless remote access.
