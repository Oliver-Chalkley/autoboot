#!/usr/bin/env bats

# Tests for scripts/flash-usb.sh argument parsing and validation.
# These tests verify the script's interface without requiring root or real devices.

SCRIPT="$BATS_TEST_DIRNAME/../../scripts/flash-usb.sh"

setup() {
    export TMPDIR
    TMPDIR=$(mktemp -d)
    echo "fake iso" > "$TMPDIR/test.iso"
}

teardown() {
    rm -rf "$TMPDIR"
}

@test "shows help with -h" {
    run bash "$SCRIPT" -h
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
    [[ "$output" == *"--iso"* ]]
    [[ "$output" == *"--device"* ]]
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

@test "fails when --iso is missing" {
    run bash "$SCRIPT" --device /dev/sdb
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --iso"* ]]
}

@test "fails when --device is missing" {
    run bash "$SCRIPT" --iso "$TMPDIR/test.iso"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Missing --device"* ]]
}

@test "fails when ISO file does not exist" {
    run bash "$SCRIPT" --iso "$TMPDIR/nonexistent.iso" --device /dev/sdb
    [ "$status" -ne 0 ]
    [[ "$output" == *"ISO file not found"* ]]
}

@test "fails when device is not a block device" {
    run bash "$SCRIPT" --iso "$TMPDIR/test.iso" --device "$TMPDIR/test.iso"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Not a block device"* ]]
}

@test "fails on unknown option" {
    run bash "$SCRIPT" --bogus-flag
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown option"* ]]
}
