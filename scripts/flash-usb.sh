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

Write an ISO image to a USB device using dd.

Options:
    --iso PATH          Path to the ISO file to write (required)
    --device PATH       Block device to write to, e.g. /dev/sdb (required)
    --yes               Skip confirmation prompt
    -h, --help          Show this help message

Example:
    sudo $(basename "$0") \\
        --iso isos/built/my-server-20240101.iso \\
        --device /dev/sdb
EOF
}

ISO=""
DEVICE=""
SKIP_CONFIRM=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --iso)      ISO="$2"; shift 2 ;;
        --device)   DEVICE="$2"; shift 2 ;;
        --yes)      SKIP_CONFIRM=true; shift ;;
        -h|--help)  usage; exit 0 ;;
        *)          error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Validate required arguments
missing=0
if [[ -z "$ISO" ]]; then error "Missing --iso"; missing=1; fi
if [[ -z "$DEVICE" ]]; then error "Missing --device"; missing=1; fi
if [[ $missing -eq 1 ]]; then usage; exit 1; fi

if [[ ! -f "$ISO" ]]; then
    error "ISO file not found: $ISO"
    exit 1
fi

if [[ ! -b "$DEVICE" ]]; then
    error "Not a block device: $DEVICE"
    exit 1
fi

# Safety check: refuse to write to mounted devices
if mount | grep -q "^$DEVICE"; then
    error "Device $DEVICE has mounted partitions. Unmount them first."
    exit 1
fi

# Show device info
info "ISO:    $ISO ($(du -h "$ISO" | cut -f1))"
info "Device: $DEVICE"
if command -v lsblk &>/dev/null; then
    lsblk -no SIZE,MODEL "$DEVICE" 2>/dev/null | while read -r line; do
        info "        $line"
    done
fi

# Confirmation
if [[ "$SKIP_CONFIRM" != true ]]; then
    warn "ALL DATA ON $DEVICE WILL BE DESTROYED!"
    echo -n "Type 'yes' to continue: "
    read -r confirm
    if [[ "$confirm" != "yes" ]]; then
        info "Aborted."
        exit 0
    fi
fi

# Unmount any partitions on the device
for part in "${DEVICE}"*; do
    if mountpoint -q "$part" 2>/dev/null || mount | grep -q "^$part "; then
        info "Unmounting $part..."
        umount "$part" 2>/dev/null || true
    fi
done

# Write ISO to device
info "Writing ISO to $DEVICE..."
dd if="$ISO" of="$DEVICE" bs=4M status=progress conv=fsync

info "Syncing..."
sync

info "Done! You can safely remove $DEVICE."
