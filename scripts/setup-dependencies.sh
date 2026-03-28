#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0")

Install system dependencies required by autoboot.

Detected OS: $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || echo "unknown")
EOF
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Detect package manager
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
else
    error "Unsupported package manager. Install these manually:"
    echo "  - xorriso"
    echo "  - curl"
    echo "  - coreutils (for dd)"
    exit 1
fi

info "Installing system dependencies..."

case "$PKG_MANAGER" in
    apt)
        sudo apt-get update -qq
        sudo apt-get install -y xorriso curl
        ;;
    dnf)
        sudo dnf install -y xorriso curl
        ;;
    pacman)
        sudo pacman -S --noconfirm libisoburn curl
        ;;
esac

# Check uv
if ! command -v uv &>/dev/null; then
    warn "uv is not installed. Install it from: https://docs.astral.sh/uv/"
    warn "  curl -LsSf https://astral.sh/uv/install.sh | sh"
else
    info "uv is already installed: $(uv --version)"
fi

info "System dependencies installed."
info ""
info "Next steps:"
info "  uv sync                          # Install Python dependencies"
info "  cp ~/.ssh/ansible.pub keys/      # Add your SSH public key"
info "  uv run autoboot new my-server --distro ubuntu"
