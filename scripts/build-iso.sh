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
Usage: $(basename "$0") [OPTIONS]

Build a customized bootable ISO with injected configuration.

Options:
    --source-iso PATH       Path to the source ISO file (required)
    --output-iso PATH       Path for the output ISO file (required)
    --config-dir PATH       Directory containing config files to inject (required)
    --injection-path PATH   Path inside ISO to place config files (required)
    --grub-sed PATTERN      Sed pattern to modify GRUB config (required)
    -h, --help              Show this help message

Example:
    $(basename "$0") \\
        --source-iso isos/downloads/ubuntu-24.04.3-live-server-amd64.iso \\
        --output-iso isos/built/my-server-20240101.iso \\
        --config-dir /tmp/autoboot-config/ \\
        --injection-path nocloud \\
        --grub-sed 's|---|autoinstall ds=nocloud\\;s=/cdrom/nocloud/ ---|g'
EOF
}

SOURCE_ISO=""
OUTPUT_ISO=""
CONFIG_DIR=""
INJECTION_PATH=""
GRUB_SED=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-iso)   SOURCE_ISO="$2"; shift 2 ;;
        --output-iso)   OUTPUT_ISO="$2"; shift 2 ;;
        --config-dir)   CONFIG_DIR="$2"; shift 2 ;;
        --injection-path) INJECTION_PATH="$2"; shift 2 ;;
        --grub-sed)     GRUB_SED="$2"; shift 2 ;;
        -h|--help)      usage; exit 0 ;;
        *)              error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Validate required arguments
missing=0
if [[ -z "$SOURCE_ISO" ]]; then error "Missing --source-iso"; missing=1; fi
if [[ -z "$OUTPUT_ISO" ]]; then error "Missing --output-iso"; missing=1; fi
if [[ -z "$CONFIG_DIR" ]]; then error "Missing --config-dir"; missing=1; fi
if [[ -z "$INJECTION_PATH" ]]; then error "Missing --injection-path"; missing=1; fi
if [[ -z "$GRUB_SED" ]]; then error "Missing --grub-sed"; missing=1; fi
if [[ $missing -eq 1 ]]; then usage; exit 1; fi

if [[ ! -f "$SOURCE_ISO" ]]; then
    error "Source ISO not found: $SOURCE_ISO"
    exit 1
fi

if [[ ! -d "$CONFIG_DIR" ]]; then
    error "Config directory not found: $CONFIG_DIR"
    exit 1
fi

if ! command -v xorriso &>/dev/null; then
    error "xorriso is not installed. Run: sudo apt install xorriso"
    exit 1
fi

# Create build directory
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

mkdir -p "$(dirname "$OUTPUT_ISO")"

# --- Modify ISO in place (preserves boot records) ---
#
# Instead of extracting, rebuilding, and losing boot records, we:
# 1. Copy the source ISO
# 2. Extract grub.cfg, modify it with sed
# 3. Use xorriso to inject config files and modified grub.cfg
#    with -boot_image any replay to preserve all boot records

info "Copying source ISO..."
cp "$SOURCE_ISO" "$OUTPUT_ISO"

# Extract and modify grub.cfg
info "Modifying GRUB configuration..."
GRUB_MODIFIED="$BUILD_DIR/grub.cfg"
if xorriso -osirrox on -indev "$SOURCE_ISO" \
    -extract /boot/grub/grub.cfg "$GRUB_MODIFIED" 2>/dev/null; then
    sed -i "$GRUB_SED" "$GRUB_MODIFIED"
else
    warn "GRUB config not found in source ISO — skipping GRUB modification"
    GRUB_MODIFIED=""
fi

# Build xorriso command to inject files
info "Injecting configuration files..."
XORRISO_CMD=(
    xorriso -dev "$OUTPUT_ISO"
    -overwrite on
)

# Inject config files into the ISO
if [[ "$INJECTION_PATH" == "." ]]; then
    # Map individual files to ISO root
    for f in "$CONFIG_DIR"/*; do
        XORRISO_CMD+=(-map "$f" "/$(basename "$f")")
    done
else
    XORRISO_CMD+=(-map "$CONFIG_DIR" "/$INJECTION_PATH")
fi

# Inject modified grub.cfg
if [[ -n "$GRUB_MODIFIED" ]]; then
    XORRISO_CMD+=(-map "$GRUB_MODIFIED" "/boot/grub/grub.cfg")
fi

# Preserve boot records
XORRISO_CMD+=(-boot_image any replay -end)

info "Rebuilding ISO with boot records preserved..."
"${XORRISO_CMD[@]}" 2>/dev/null

info "Built ISO: $OUTPUT_ISO"
info "Size: $(du -h "$OUTPUT_ISO" | cut -f1)"
