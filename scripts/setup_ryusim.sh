#!/usr/bin/env bash
# scripts/setup_ryusim.sh — Install the RyuSim binary
set -euo pipefail

if command -v ryusim &>/dev/null; then
    echo "RyuSim already installed: $(ryusim --version 2>&1 || echo unknown)"
    exit 0
fi

echo "Installing RyuSim..."
curl -fsSL https://ryusim.seiraiyu.com/install.sh | bash

echo "RyuSim installed: $(ryusim --version 2>&1 || echo unknown)"
