#!/usr/bin/env bats

# Tests for scripts/build-iso.sh argument parsing and validation.
# These tests verify the script's interface without requiring xorriso.

SCRIPT="$BATS_TEST_DIRNAME/../../scripts/build-iso.sh"

setup() {
    export TMPDIR
    TMPDIR=$(mktemp -d)
    # Create a fake source ISO
    echo "fake iso" > "$TMPDIR/source.iso"
    # Create a fake config dir
    mkdir -p "$TMPDIR/config"
    echo "test config" > "$TMPDIR/config/user-data"
}

teardown() {
    rm -rf "$TMPDIR"
}

@test "shows help with -h" {
    run bash "$SCRIPT" -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
    [[ "$output" == *"--source-iso"* ]]
}

@test "shows help with --help" {
    run bash "$SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "fails with no arguments" {
    run bash "$SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing"* ]]
}

@test "fails when --source-iso is missing" {
    run bash "$SCRIPT" \
        --output-iso "$TMPDIR/out.iso" \
        --config-dir "$TMPDIR/config" \
        --injection-path nocloud \
        --grub-sed 's|---|test---|g'
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --source-iso"* ]]
}

@test "fails when --output-iso is missing" {
    run bash "$SCRIPT" \
        --source-iso "$TMPDIR/source.iso" \
        --config-dir "$TMPDIR/config" \
        --injection-path nocloud \
        --grub-sed 's|---|test---|g'
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --output-iso"* ]]
}

@test "fails when --config-dir is missing" {
    run bash "$SCRIPT" \
        --source-iso "$TMPDIR/source.iso" \
        --output-iso "$TMPDIR/out.iso" \
        --injection-path nocloud \
        --grub-sed 's|---|test---|g'
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --config-dir"* ]]
}

@test "fails when --injection-path is missing" {
    run bash "$SCRIPT" \
        --source-iso "$TMPDIR/source.iso" \
        --output-iso "$TMPDIR/out.iso" \
        --config-dir "$TMPDIR/config" \
        --grub-sed 's|---|test---|g'
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --injection-path"* ]]
}

@test "fails when --grub-sed is missing" {
    run bash "$SCRIPT" \
        --source-iso "$TMPDIR/source.iso" \
        --output-iso "$TMPDIR/out.iso" \
        --config-dir "$TMPDIR/config" \
        --injection-path nocloud
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --grub-sed"* ]]
}

@test "fails when source ISO does not exist" {
    run bash "$SCRIPT" \
        --source-iso "$TMPDIR/nonexistent.iso" \
        --output-iso "$TMPDIR/out.iso" \
        --config-dir "$TMPDIR/config" \
        --injection-path nocloud \
        --grub-sed 's|---|test---|g'
    [ "$status" -ne 0 ]
    [[ "$output" == *"Source ISO not found"* ]]
}

@test "fails when config directory does not exist" {
    run bash "$SCRIPT" \
        --source-iso "$TMPDIR/source.iso" \
        --output-iso "$TMPDIR/out.iso" \
        --config-dir "$TMPDIR/no-such-dir" \
        --injection-path nocloud \
        --grub-sed 's|---|test---|g'
    [ "$status" -ne 0 ]
    [[ "$output" == *"Config directory not found"* ]]
}

@test "fails on unknown option" {
    run bash "$SCRIPT" --bogus-flag
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown option"* ]]
}
