#!/usr/bin/env bash
set -euo pipefail

# End-to-end test runner for autoboot.
#
# This script orchestrates the full E2E flow:
#   1. Build an autoboot ISO for a test machine config
#   2. Boot a QEMU VM from the ISO via Packer
#   3. Validate the install with Ansible
#
# Prerequisites:
#   - packer, qemu-system-x86_64, ansible, xorriso
#   - A source ISO downloaded (or use --skip-build with a pre-built ISO)
#   - An SSH keypair at keys/ansible and keys/ansible.pub
#
# Usage:
#   ./tests/e2e/run-e2e.sh --distro ubuntu [--version 24.04.3] [--skip-build]
#   ./tests/e2e/run-e2e.sh --distro debian [--version 12.9] [--skip-build]

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[E2E]${NC} $*"; }
warn()  { echo -e "${YELLOW}[E2E]${NC} $*"; }
error() { echo -e "${RED}[E2E]${NC} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DISTRO=""
VERSION=""
SKIP_BUILD=false
ISO_PATH=""
MACHINE_NAME="e2e-test"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Run end-to-end tests for autoboot.

Options:
    --distro NAME       Distro to test: ubuntu or debian (required)
    --version VER       Distro version (default: latest supported)
    --iso PATH          Use a specific pre-built ISO instead of building
    --skip-build        Skip the build step (use existing built ISO)
    --machine NAME      Machine config name (default: e2e-test)
    -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --distro)      DISTRO="$2"; shift 2 ;;
        --version)     VERSION="$2"; shift 2 ;;
        --iso)         ISO_PATH="$2"; shift 2 ;;
        --skip-build)  SKIP_BUILD=true; shift ;;
        --machine)     MACHINE_NAME="$2"; shift 2 ;;
        -h|--help)     usage; exit 0 ;;
        *)             error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

if [[ -z "$DISTRO" ]]; then
    error "Missing --distro"
    usage
    exit 1
fi

# --- Check prerequisites ---

check_command() {
    if ! command -v "$1" &>/dev/null; then
        error "Required command not found: $1"
        error "Install it before running E2E tests."
        exit 1
    fi
}

info "Checking prerequisites..."
check_command packer
check_command qemu-system-x86_64
check_command ansible-playbook

if [[ ! -f "$PROJECT_ROOT/keys/ansible.pub" ]]; then
    error "SSH public key not found at keys/ansible.pub"
    error "Generate one with: ssh-keygen -t ed25519 -f keys/ansible -N ''"
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/keys/ansible" ]]; then
    error "SSH private key not found at keys/ansible"
    error "Generate one with: ssh-keygen -t ed25519 -f keys/ansible -N ''"
    exit 1
fi

# --- Build ISO if needed ---

cd "$PROJECT_ROOT"

if [[ -n "$ISO_PATH" ]]; then
    if [[ ! -f "$ISO_PATH" ]]; then
        error "ISO not found: $ISO_PATH"
        exit 1
    fi
    info "Using provided ISO: $ISO_PATH"
elif [[ "$SKIP_BUILD" == true ]]; then
    # Find the latest built ISO for this machine
    ISO_PATH=$(find isos/built/ -maxdepth 1 -name "${MACHINE_NAME}-*.iso" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2 || true)
    if [[ -z "$ISO_PATH" ]]; then
        error "No built ISO found for ${MACHINE_NAME}. Run without --skip-build first."
        exit 1
    fi
    info "Using existing ISO: $ISO_PATH"
else
    info "Creating test machine config..."
    VERSION_FLAG=""
    if [[ -n "$VERSION" ]]; then
        VERSION_FLAG="--version $VERSION"
    fi

    # Remove existing test config if present
    rm -rf "configs/${MACHINE_NAME}"

    # shellcheck disable=SC2086
    uv run autoboot new "$MACHINE_NAME" --distro "$DISTRO" $VERSION_FLAG
    info "Config created at configs/${MACHINE_NAME}/config.yaml"

    info "Downloading source ISO..."
    uv run autoboot download "$MACHINE_NAME"

    info "Building customized ISO..."
    uv run autoboot build "$MACHINE_NAME"

    ISO_PATH=$(find isos/built/ -maxdepth 1 -name "${MACHINE_NAME}-*.iso" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2 || true)
    if [[ -z "$ISO_PATH" ]]; then
        error "Build produced no ISO output."
        exit 1
    fi
    info "Built ISO: $ISO_PATH"
fi

# --- Run Packer ---

PACKER_TEMPLATE=""
case "$DISTRO" in
    ubuntu) PACKER_TEMPLATE="tests/e2e/ubuntu-autoinstall.pkr.hcl" ;;
    debian) PACKER_TEMPLATE="tests/e2e/debian-preseed.pkr.hcl" ;;
    *)      error "Unsupported distro for E2E: $DISTRO"; exit 1 ;;
esac

# Clean previous output
rm -rf "tests/e2e/output/$DISTRO"

info "Initializing Packer..."
packer init "$PACKER_TEMPLATE"

info "Running Packer (this will take ~15-30 minutes)..."
info "The VM will boot, install the OS, and then run validation."
packer build \
    -var "iso_path=$ISO_PATH" \
    -var "ssh_private_key_file=$PROJECT_ROOT/keys/ansible" \
    "$PACKER_TEMPLATE"

info "=== E2E test passed for $DISTRO ==="

# --- Cleanup ---

info "Cleaning up test artifacts..."
rm -rf "tests/e2e/output/$DISTRO"
rm -rf "configs/${MACHINE_NAME}"

info "Done."
