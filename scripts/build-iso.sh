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

info "Extracting source ISO..."
xorriso -osirrox on -indev "$SOURCE_ISO" -extract / "$BUILD_DIR/iso" 2>/dev/null

info "Making ISO writable..."
chmod -R u+w "$BUILD_DIR/iso"

info "Injecting configuration files..."
mkdir -p "$BUILD_DIR/iso/$INJECTION_PATH"
cp -r "$CONFIG_DIR"/* "$BUILD_DIR/iso/$INJECTION_PATH/"

info "Modifying GRUB configuration..."
if [[ -f "$BUILD_DIR/iso/boot/grub/grub.cfg" ]]; then
    sed -i "$GRUB_SED" "$BUILD_DIR/iso/boot/grub/grub.cfg"
else
    warn "GRUB config not found at boot/grub/grub.cfg — skipping GRUB modification"
fi

info "Rebuilding ISO..."
mkdir -p "$(dirname "$OUTPUT_ISO")"

# Build with both BIOS and UEFI boot support
xorriso -as mkisofs \
    -r -V "AUTOBOOT" \
    -o "$OUTPUT_ISO" \
    -J -joliet-long \
    -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin 2>/dev/null || \
xorriso -as mkisofs \
    -r -V "AUTOBOOT" \
    -o "$OUTPUT_ISO" \
    -J -joliet-long \
    -partition_offset 16 \
    -append_partition 2 0xef "$BUILD_DIR/iso/boot/grub/efi.img" 2>/dev/null || true

# Primary build command
xorriso -as mkisofs \
    -r -V "AUTOBOOT" \
    -o "$OUTPUT_ISO" \
    -J -joliet-long \
    "$BUILD_DIR/iso"

info "Built ISO: $OUTPUT_ISO"
info "Size: $(du -h "$OUTPUT_ISO" | cut -f1)"
