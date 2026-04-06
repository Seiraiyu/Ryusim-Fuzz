#!/usr/bin/env bash
# scripts/setup_chimera.sh — Build ChiGen from the chimera submodule
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
CHIMERA_DIR="$REPO_DIR/chimera"

if [ ! -f "$CHIMERA_DIR/CMakeLists.txt" ] && [ ! -d "$CHIMERA_DIR/src" ]; then
    echo "Error: chimera submodule not initialized. Run: git submodule update --init" >&2
    exit 1
fi

echo "Building ChiGen from $CHIMERA_DIR..."
cd "$CHIMERA_DIR"
cmake -S src -B build/ -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)" -C build/

echo "ChiGen built: $CHIMERA_DIR/build/Chimera"
"$CHIMERA_DIR/build/Chimera" --help || true
