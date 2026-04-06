# CLAUDE.md

## Project Purpose

RyuSim-Fuzz is a differential fuzzing harness for [RyuSim](https://github.com/Seiraiyu/RyuSimAlt). It generates thousands of Verilog designs via Chimera (grammar-based) and VlogHammer (expression-level), simulates each with RyuSim, Verilator, and Icarus Verilog through cocotb, and flags any discrepancies via VCD waveform comparison.

## Architecture

Two generators feed into a shared harness:

| Directory | Source | Purpose |
|-----------|--------|---------|
| `chimera/` | [lac-dcc/chimera](https://github.com/lac-dcc/chimera) (submodule) | Grammar-based Verilog design generator |
| `vloghammer/` | [YosysHQ/VlogHammer](https://github.com/YosysHQ/VlogHammer) (submodule) | Expression-level differential test generator |
| `harness/` | This repo | Shared orchestration: generate → simulate → compare → triage |

### Pipeline

1. **Generate** — Chimera/VlogHammer produce `.sv`/`.v` files
2. **Filter** — Discard designs with unsupported constructs (`initial`, `$display`, `#` delays)
3. **Simulate** — Create temp cocotb env, run `make SIM=ryusim`, `make SIM=verilator`, `make SIM=icarus`
4. **Compare** — `vcddiff` between RyuSim VCD and each reference
5. **Triage** — Save findings to `findings/` with metadata
6. **Report** — Auto-file GitHub issues on RyuSimAlt

## Key Constraints

- All simulation goes through cocotb Makefiles (`SIM=` variable) — same Makefile, three invocations
- RyuSim only supports synthesizable constructs — generated designs are filtered
- VCD waveform diff is the comparison oracle

## Commands

```bash
# Setup
bash scripts/setup_chimera.sh    # Build ChiGen from submodule
bash scripts/setup_vloghammer.sh # Build VlogHammer from submodule
bash scripts/setup_ryusim.sh     # Install RyuSim binary

# Run fuzzing
python run_fuzz.py --all --count 100
python run_fuzz.py --generator chimera --count 50 --seed 42
python run_fuzz.py --generator vloghammer --count 200
python run_fuzz.py --all --count 100 --file-issues --output results/fuzz.json

# Reproduce a finding
python run_fuzz.py --reproduce findings/2026-04-06-0001/
```

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| `ryusim` | Simulator under test | `scripts/setup_ryusim.sh` |
| `cocotb` | Simulation framework (Seiraiyu fork) | `pip install -r requirements.txt` |
| `verilator` | Reference simulator | `apt install verilator` |
| `iverilog` | Reference simulator | `apt install iverilog` |
| `vcddiff` | VCD comparison | `pip install vcdvcd` (includes vcddiff) |
| `cmake`, `g++` | Build ChiGen | `apt install cmake g++` |
| `clang` | Build VlogHammer generate.cc | `apt install clang` |
