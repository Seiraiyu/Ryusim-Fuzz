#!/usr/bin/env bash
# scripts/setup_vloghammer.sh — Build VlogHammer's generator from the submodule
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
VLOGHAMMER_DIR="$REPO_DIR/vloghammer"

if [ ! -f "$VLOGHAMMER_DIR/Makefile" ]; then
    echo "Error: vloghammer submodule not initialized. Run: git submodule update --init" >&2
    exit 1
fi

GEN_CC="$VLOGHAMMER_DIR/scripts/generate.cc"
GEN_BIN="$VLOGHAMMER_DIR/scripts/generate"

if [ ! -f "$GEN_CC" ]; then
    echo "Error: generate.cc not found at $GEN_CC" >&2
    exit 1
fi

echo "Building VlogHammer generator..."
clang++ -o "$GEN_BIN" "$GEN_CC"

echo "VlogHammer generator built: $GEN_BIN"

# Pre-generate RTL files
echo "Generating RTL test cases..."
cd "$VLOGHAMMER_DIR"
mkdir -p rtl
"$GEN_BIN" || true

echo "VlogHammer setup complete. Generated files in $VLOGHAMMER_DIR/rtl/"
ls rtl/*.v 2>/dev/null | wc -l | xargs -I{} echo "{} test files generated"
